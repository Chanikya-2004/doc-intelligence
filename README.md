# Doc-Intelligence — PDF Document Intelligence Platform

A full-stack RAG (Retrieval-Augmented Generation) application that lets you upload PDF documents and ask questions about them in natural language. Built as a portfolio project demonstrating modern AI/ML engineering skills.

## Demo
- Upload any PDF document
- Ask questions in natural language
- Get grounded answers with exact page citations
- Multi-turn conversation memory — ask follow-up questions naturally

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite, Axios, CSS Modules |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 18 + pgvector |
| Embeddings | Google Gemini (gemini-embedding-001, 768 dimensions) |
| Generation | Google Gemini (gemini-2.5-flash) |
| Vector Search | pgvector HNSW index (cosine similarity) |

## Key Features
- **Semantic Search** — finds relevant content by meaning, not just keywords
- **Multi-turn Memory** — conversation history stored in PostgreSQL, follow-up questions understood in context
- **Query Rewriting** — ambiguous follow-ups rewritten into standalone search queries using Gemini
- **Page Citations** — every answer cites the exact page it came from
- **Rate Limit Handling** — graceful 429/503 error handling with retry logic

## Project Structure
doc-intelligence/

├── backend/

│   ├── main.py

│   ├── services/

│   │   ├── document_parser.py

│   │   ├── chunker.py

│   │   ├── embedder.py

│   │   ├── vector_store.py

│   │   ├── generator.py

│   │   └── session_store.py

│   └── .env.example

├── frontend/

│   ├── src/

│   │   ├── App.jsx

│   │   └── components/

│   │       ├── ChatWindow.jsx

│   │       ├── DocumentSidebar.jsx

│   │       ├── UploadArea.jsx

│   │       └── CitationChip.jsx

│   └── package.json

└── README.md

## Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 18 with pgvector extension
- Google Gemini API key (free at https://aistudio.google.com/apikey)

### Backend Setup
cd backend

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env

uvicorn main:app --reload

### Frontend Setup
cd frontend

npm install

npm run dev

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /upload | Upload and ingest a PDF |
| POST | /chat | Ask a question, get a grounded answer |
| GET | /search | Raw semantic search |
| GET | /documents | List all uploaded documents |
| DELETE | /documents/{filename} | Remove a document |
| GET | /health | System health check |

## What I Learned Building This
- RAG pipeline architecture (parse, chunk, embed, store, retrieve, generate)
- pgvector HNSW indexing for approximate nearest neighbour search
- Prompt engineering for grounded citation-aware answers
- Session memory design with PostgreSQL
- Query rewriting for multi-turn conversation
- FastAPI async patterns and error handling
- React state management for real-time chat UI
