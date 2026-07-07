# main.py — Complete Day 4 version

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from services.document_parser import DocumentParser
from services.chunker import SlidingWindowChunker
from services.embedder import Embedder
from services.vector_store import VectorStore
from services.generator import Generator
from services.session_store import SessionStore

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & service initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PDF Document Intelligence Platform",
    description="Upload PDFs. Ask questions. Get grounded answers with citations.",
    version="0.4.0",
)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

document_parser = DocumentParser()
chunker = SlidingWindowChunker(chunk_size=1000, overlap=200)
embedder = Embedder()
vector_store = VectorStore()
generator = Generator()     # NEW: Gemini Flash generation service
session_store = SessionStore()

# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for POST /chat"""
    question: str = Field(
        ...,
        min_length=5,
        description="Your question about the uploaded documents",
        example="What programming languages does the candidate know?",
    )
    n_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of context chunks to retrieve (more = richer context)",
    )
    filename_filter: Optional[str] = Field(
        default=None,
        description="Limit search to a specific document filename",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session ID. Omit on first message to start a new session.",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    api_key_set = bool(
        os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    )
    return {
        "status": "ok",
        "google_api_key_configured": api_key_set,
        "vector_store": vector_store.get_stats(),
    }

@app.get("/documents", tags=["Ingestion"])
async def list_documents():
    """Fetch list of all documents currently in the vector store."""
    stats = vector_store.get_stats()
    return JSONResponse(
        status_code=200,
        content={
            "documents": stats.get("documents", []),
            "total_vectors": stats.get("total_vectors", 0),
        },
    )


# ---------------------------------------------------------------------------
# Upload & Ingest (unchanged from Day 3)
# ---------------------------------------------------------------------------

@app.post("/upload", tags=["Ingestion"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF and run the full ingestion pipeline:
    Parse → Chunk → Embed → Store in ChromaDB.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file: '{file.filename}'. Only .pdf files accepted.",
        )

    save_path = UPLOAD_DIR / file.filename

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        await file.close()

    try:
        parsed_doc = document_parser.parse(save_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF parsing failed: {e}")

    try:
        chunks = chunker.chunk_document(parsed_doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {e}")

    if not chunks:
        raise HTTPException(status_code=422, detail="No text chunks produced.")

    try:
        embedding_results = embedder.embed_chunks(chunks)
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Embedding API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")

    try:
        stored_count = vector_store.store(embedding_results)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Vector storage failed: {e}")

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "filename": parsed_doc.filename,
            "pipeline_summary": {
                "pages_parsed": parsed_doc.total_pages,
                "total_characters": parsed_doc.total_characters,
                "chunks_created": len(chunks),
                "vectors_stored": stored_count,
                "vector_dimensions": (
                    embedding_results[0].dimensions if embedding_results else 0
                ),
                "total_vectors_in_store": vector_store.get_stats()["total_vectors"],
            },
            "message": (
                f"'{parsed_doc.filename}' ingested successfully. "
                f"{stored_count} vectors stored."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Search (unchanged from Day 3)
# ---------------------------------------------------------------------------

@app.get("/search", tags=["Search"])
async def search_documents(
    q: str = Query(..., description="Search query", min_length=3),
    n: int = Query(default=5, ge=1, le=20),
    filename: Optional[str] = Query(default=None),
):
    """Raw semantic search — returns chunks without LLM generation."""
    try:
        query_vector = embedder.embed_query(q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    try:
        results = vector_store.search(
            query_vector=query_vector,
            n_results=n,
            filename_filter=filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(
        status_code=200,
        content={
            "query": q,
            "total_results": len(results),
            "results": [r.to_dict() for r in results],
        },
    )


# ---------------------------------------------------------------------------
# Chat — NEW TODAY
# ---------------------------------------------------------------------------

@app.post("/chat", tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Ask a question about your uploaded documents and get a grounded answer.

    Now session-aware: pass a session_id to continue a conversation with
    memory, or omit it to start a new session (one will be created and
    returned in the response).
    """

    # ── Step 0: Resolve the session ─────────────────────────────────────
    session_id = request.session_id
    if not session_id or not session_store.session_exists(session_id):
        session_id = session_store.create_session()

    # Save the user's message right away, so it's part of history
    # even if generation fails later.
    session_store.add_message(session_id, "user", request.question)
    # ── Step 0b: Rewrite follow-up questions into standalone queries ──────
    history = session_store.get_recent_messages(session_id, limit=4)
    search_query = generator.rewrite_query(request.question, history)
    logger.info("Original: '%s' | Rewritten: '%s' | History: %d msgs", 
                request.question, search_query, len(history))

    # ── Step 1: Embed the question ────────────────────────────────────────
    try:
        query_vector = embedder.embed_query(search_query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query embedding failed: {e}")

    # ── Step 2: Retrieve relevant chunks ─────────────────────────────────
    try:
        search_results = vector_store.search(
            query_vector=query_vector,
            n_results=request.n_results,
            filename_filter=request.filename_filter,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail="No documents found. Upload a PDF first.",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Step 3 & 4: Generate grounded answer ─────────────────────────────
    try:
        chat_response = generator.generate(
            question=request.question,
            search_results=search_results,
            history=history,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Generation error: {e}")
    except Exception as e:
        logger.exception("Unexpected generation error")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # ── Save the assistant's reply to history ──────────────────────────
    session_store.add_message(session_id, "assistant", chat_response.answer)

    # ── Return full response ──────────────────────────────────────────────
    return JSONResponse(
        status_code=200,
        content={
            "question": request.question,
            "session_id": session_id,
            **chat_response.to_dict(),
        },
    )


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------

@app.delete("/documents/{filename}", tags=["Ingestion"])
async def delete_document(filename: str):
    """Remove all vectors for a document. Use before re-uploading an updated PDF."""
    deleted = vector_store.delete_document(filename)
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No vectors found for '{filename}'.",
        )
    return {"status": "deleted", "filename": filename, "vectors_removed": deleted}