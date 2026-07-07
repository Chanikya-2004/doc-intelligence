# services/session_store.py — manages chat session memory in Postgres

import logging
import uuid
from typing import List, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from .vector_store import VectorStore  # reuse same connection pattern

logger = logging.getLogger(__name__)


class SessionStore:
    """Handles creating chat sessions and reading/writing messages."""

    def __init__(self):
        # Reuse the same connection params VectorStore already validated
        vs = VectorStore()
        self.conn_params = vs.conn_params

    def _connect(self):
        return psycopg2.connect(**self.conn_params)

    def create_session(self) -> str:
        """Create a new chat session and return its UUID as a string."""
        session_id = str(uuid.uuid4())
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_sessions (id) VALUES (%s)",
            (session_id,),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Created new chat session: %s", session_id)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM chat_sessions WHERE id = %s", (session_id,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Save one message (role is 'user' or 'assistant')."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content),
        )
        conn.commit()
        cur.close()
        conn.close()

    def get_recent_messages(self, session_id: str, limit: int = 4) -> List[Dict[str, str]]:
        """
        Fetch the last `limit` messages for a session, oldest first.
        Returns a list of {"role": ..., "content": ...} dicts.
        """
        conn = self._connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, limit),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Reverse so oldest comes first (we fetched newest-first via DESC)
        return list(reversed(rows))