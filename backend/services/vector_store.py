# services/vector_store.py — Postgres + pgvector version

import logging
import os
from typing import List, Dict, Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from .embedder import EmbeddingResult

load_dotenv()
logger = logging.getLogger(__name__)


class SearchResult:
    """A single search result returned from Postgres."""
    def __init__(self, chunk_id, text, source_filename, page_number, distance):
        self.chunk_id = chunk_id
        self.text = text
        self.source_filename = source_filename
        self.page_number = page_number
        self.distance = distance
        self.relevance_score = round(1 / (1 + distance), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_filename": self.source_filename,
            "page_number": self.page_number,
            "relevance_score": self.relevance_score,
        }


class VectorStore:
    """
    Postgres + pgvector backed vector store.
    Same public interface as the old ChromaDB version:
    store(), search(), get_stats(), delete_document().
    """

    def __init__(self, db_path: str = None):
        # db_path kept as an unused param so old call sites (VectorStore()) still work
        self.conn_params = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": os.getenv("POSTGRES_PORT", "5432"),
            "dbname": os.getenv("POSTGRES_DB", "doc_intelligence"),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
        }
        try:
            conn = self._connect()
            conn.close()
            logger.info("VectorStore initialized. Connected to Postgres.")
        except Exception as e:
            raise RuntimeError(f"Could not connect to Postgres: {e}") from e

    def _connect(self):
        return psycopg2.connect(**self.conn_params)

    # -----------------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------------

    def store(self, embedding_results: List[EmbeddingResult]) -> int:
        if not embedding_results:
            raise ValueError("Cannot store empty list of embedding results.")

        rows = []
        for result in embedding_results:
            chunk = result.chunk
            rows.append((
                chunk.chunk_id,
                chunk.source_filename,
                chunk.page_number,
                chunk.start_char,
                chunk.end_char,
                chunk.text,
                result.vector,
            ))

        try:
            conn = self._connect()
            cur = conn.cursor()
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO chunks
                    (chunk_id, source_filename, page_number, start_char, end_char, text, embedding)
                VALUES %s
                ON CONFLICT (source_filename, chunk_id)
                DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    page_number = EXCLUDED.page_number,
                    start_char = EXCLUDED.start_char,
                    end_char = EXCLUDED.end_char
                """,
                rows,
                template="(%s, %s, %s, %s, %s, %s, %s::vector)",
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Stored %d chunks for '%s'.", len(rows), rows[0][1])
            return len(rows)
        except Exception as e:
            raise RuntimeError(f"Postgres storage failed: {e}") from e

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    def search(
        self,
        query_vector: List[float],
        n_results: int = 5,
        filename_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        try:
            conn = self._connect()
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM chunks")
            total = cur.fetchone()[0]
            if total == 0:
                cur.close()
                conn.close()
                raise ValueError("The vector store is empty. Upload at least one PDF before searching.")

            vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

            if filename_filter:
                cur.execute(
                    """
                    SELECT chunk_id, text, source_filename, page_number,
                           embedding <=> %s::vector AS distance
                    FROM chunks
                    WHERE source_filename = %s
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector_str, filename_filter, n_results),
                )
            else:
                cur.execute(
                    """
                    SELECT chunk_id, text, source_filename, page_number,
                           embedding <=> %s::vector AS distance
                    FROM chunks
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector_str, n_results),
                )

            rows = cur.fetchall()
            cur.close()
            conn.close()

            return [
                SearchResult(
                    chunk_id=row[0],
                    text=row[1],
                    source_filename=row[2],
                    page_number=row[3],
                    distance=row[4],
                )
                for row in rows
            ]
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Postgres query failed: {e}") from e

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM chunks")
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT source_filename, COUNT(*) FROM chunks GROUP BY source_filename"
            )
            documents = [
                {"filename": fname, "chunk_count": count}
                for fname, count in cur.fetchall()
            ]
            cur.close()
            conn.close()

            return {
                "collection_name": "chunks",
                "total_vectors": total,
                "db_path": "postgres",
                "documents": documents,
            }
        except Exception as e:
            logger.error("get_stats failed: %s", e)
            return {"collection_name": "chunks", "total_vectors": 0, "db_path": "postgres", "documents": []}

    def delete_document(self, filename: str) -> int:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("DELETE FROM chunks WHERE source_filename = %s", (filename,))
            deleted = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Deleted %d chunks for document '%s'", deleted, filename)
            return deleted
        except Exception as e:
            raise RuntimeError(f"Postgres delete failed: {e}") from e