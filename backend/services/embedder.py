# services/embedder.py

import logging
import time
import os
from typing import List

from google import genai
from google.genai import types as genai_types

from .chunker import TextChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
MAX_BATCH_SIZE = 100
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0


class EmbeddingResult:
    def __init__(self, chunk: TextChunk, vector: List[float]):
        self.chunk = chunk
        self.vector = vector
        self.dimensions = len(vector)

    def __repr__(self) -> str:
        return (
            f"EmbeddingResult(chunk_id={self.chunk.chunk_id}, "
            f"dims={self.dimensions}, "
            f"page={self.chunk.page_number})"
        )


class Embedder:
    def __init__(self, api_key: str | None = None):
        resolved_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. "
                "Either pass api_key= to Embedder() or set the environment variable."
            )
        self.client = genai.Client(api_key=resolved_key)
        logger.info("Embedder initialized with model: %s", EMBEDDING_MODEL)

    def embed_chunks(self, chunks: List[TextChunk]) -> List[EmbeddingResult]:
        if not chunks:
            logger.warning("embed_chunks called with empty list, returning []")
            return []

        for chunk in chunks:
            if not chunk.text.strip():
                raise ValueError(
                    f"Chunk {chunk.chunk_id} from '{chunk.source_filename}' "
                    "has empty text. Cannot embed empty strings."
                )

        results: List[EmbeddingResult] = []
        total_chunks = len(chunks)
        processed = 0

        logger.info(
            "Embedding %d chunks in batches of %d...", total_chunks, MAX_BATCH_SIZE
        )

        for batch_start in range(0, total_chunks, MAX_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + MAX_BATCH_SIZE]
            batch_texts = [chunk.text for chunk in batch]

            vectors = self._embed_batch_with_retry(batch_texts, batch_start)

            for chunk, vector in zip(batch, vectors):
                results.append(EmbeddingResult(chunk=chunk, vector=vector))

            processed += len(batch)
            logger.info(
                "  Progress: %d / %d chunks embedded", processed, total_chunks
            )

        return results

    def embed_query(self, query_text: str) -> List[float]:
        if not query_text.strip():
            raise ValueError("Query text cannot be empty.")

        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query_text,
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )
        return response.embeddings[0].values

    def _embed_batch_with_retry(
        self, texts: List[str], batch_start_idx: int
    ) -> List[List[float]]:
        delay = RETRY_DELAY_SECONDS

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                response = self.client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=texts,
                    config=genai_types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=EMBEDDING_DIMENSIONS,
                    ),
                )

                if not response.embeddings:
                    raise RuntimeError(
                        f"API returned empty embeddings list for batch "
                        f"starting at index {batch_start_idx}."
                    )

                vectors = [emb.values for emb in response.embeddings]

                for i, vec in enumerate(vectors):
                    if len(vec) != EMBEDDING_DIMENSIONS:
                        raise RuntimeError(
                            f"Vector at position {i} has {len(vec)} dimensions, "
                            f"expected {EMBEDDING_DIMENSIONS}."
                        )

                return vectors

            except Exception as e:
                error_str = str(e).lower()

                if any(kw in error_str for kw in ["invalid", "malformed", "400"]):
                    raise RuntimeError(
                        f"Non-retryable embedding error for batch at index "
                        f"{batch_start_idx}: {e}"
                    ) from e

                if attempt < RETRY_ATTEMPTS:
                    logger.warning(
                        "Embedding attempt %d/%d failed. Retrying in %.1fs. Error: %s",
                        attempt, RETRY_ATTEMPTS, delay, e,
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise RuntimeError(
                        f"All {RETRY_ATTEMPTS} embedding attempts failed for batch "
                        f"at index {batch_start_idx}. Last error: {e}"
                    ) from e

        raise RuntimeError("Unexpected exit from retry loop.")