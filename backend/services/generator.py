# services/generator.py

import logging
import os
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from google import genai
from google.genai import types as genai_types

from .vector_store import SearchResult

logger = logging.getLogger(__name__)

GENERATION_MODEL = "gemini-2.5-flash"
DEFAULT_CONTEXT_CHUNKS = 5


@dataclass
class ChatResponse:
    answer: str
    sources: List[Dict[str, Any]]
    model: str
    chunks_used: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "model": self.model,
            "chunks_used": self.chunks_used,
        }


class Generator:

    def __init__(self, api_key: str | None = None):
        resolved_key = (
            api_key
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not resolved_key:
            raise EnvironmentError(
                "No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env"
            )
        self.client = genai.Client(api_key=resolved_key)
        logger.info("Generator initialized with model: %s", GENERATION_MODEL)

    def rewrite_query(
        self,
        question: str,
        history: List[Dict[str, str]],
    ) -> str:
        """Rewrite ambiguous follow-up into standalone search query."""
        if not history:
            return question

        recent = history[-2:]
        history_text = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in recent
        )

        prompt = f"""Conversation so far:
{history_text}

Latest user message: {question}

Rewrite the latest user message as a complete, standalone search query
that makes sense without the conversation above.
Do NOT answer the question — only rewrite it.
If already standalone and clear, return it unchanged.
Return ONLY the rewritten query, nothing else."""

        try:
            response = self.client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=128,
                ),
            )
            rewritten = response.text.strip()
            logger.info("Query rewritten: '%s' -> '%s'", question[:50], rewritten[:50])
            return rewritten if rewritten else question
        except Exception as e:
            logger.warning("Query rewrite failed, using original: %s", e)
            return question

    def generate(
        self,
        question: str,
        search_results: List[SearchResult],
        history: List[Dict[str, str]] = None,
    ) -> ChatResponse:
        """Generate a grounded answer from retrieved context chunks."""
        if not question.strip():
            raise ValueError("Question cannot be empty.")
        if not search_results:
            raise ValueError("No search results provided.")

        context = self._build_context(search_results)
        prompt = self._build_prompt(question, context, history)

        logger.info(
            "Generating answer for: '%s...' using %d chunks",
            question[:60], len(search_results)
        )

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=GENERATION_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=self._system_prompt(),
                        temperature=0.2,
                        max_output_tokens=1024,
                    ),
                )
                answer_text = response.text.strip()
                break
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        logger.warning("Rate limited. Waiting %ds...", wait)
                        time.sleep(wait)
                        continue
                    raise RuntimeError(
                        "Daily AI limit reached. Free tier allows 1500 "
                        "requests/day. Try again tomorrow."
                    )
                raise RuntimeError(f"Gemini generation failed: {e}") from e
        else:
            raise RuntimeError(
                f"Gemini generation failed after 3 attempts: {last_error}"
            )

        sources = self._build_sources(search_results)

        return ChatResponse(
            answer=answer_text,
            sources=sources,
            model=GENERATION_MODEL,
            chunks_used=len(search_results),
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return """You are a precise document analysis assistant.

Your job is to answer questions based ONLY on the context chunks provided.
Each context chunk includes a page number and source filename.

Rules you must follow:
1. BASE your answer strictly on the provided context. Do not use outside knowledge.
2. ALWAYS mention the page number when citing information, e.g. "(Page 1)".
3. ADAPT your style to the question:
   - Factual/list questions -> bullet points
   - Explanatory questions -> short paragraphs
   - Yes/no questions -> direct answer first, then brief explanation
4. If the context does not contain enough information to answer the question,
   say exactly: "The provided document does not contain information about this topic."
5. Do not make up information. Do not speculate.
6. Keep answers concise — no unnecessary padding or filler sentences.
7. If multiple chunks support the answer, synthesize them into one coherent response.
8. If conversation history is provided, use it to understand follow-up questions
   but still base your answer ONLY on the document context chunks."""

    def _build_context(self, search_results: List[SearchResult]) -> str:
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[Context {i}]\n"
                f"Source: {result.source_filename} | Page: {result.page_number}\n"
                f"Relevance: {result.relevance_score}\n"
                f"Content: {result.text}\n"
            )
        return "\n---\n".join(context_parts)

    def _build_prompt(
        self,
        question: str,
        context: str,
        history: List[Dict[str, str]] = None,
    ) -> str:
        """Includes last 3 conversation turns as sliding context window."""
        history_block = ""
        if history:
            recent = history[-3:]
            lines = []
            for turn in recent:
                role_label = "User" if turn["role"] == "user" else "Assistant"
                lines.append(f"[{role_label}]: {turn['content']}")
            history_block = (
                "Conversation history:\n"
                + "\n".join(lines)
                + "\n\n---\n\n"
            )

        return f"""{history_block}Here are the relevant sections from the document:

{context}

---

Based on the above context only, please answer this question:
{question}"""

    def _build_sources(
        self, search_results: List[SearchResult]
    ) -> List[Dict[str, Any]]:
        seen = set()
        sources = []
        for result in search_results:
            key = f"{result.source_filename}::{result.page_number}"
            if key not in seen:
                seen.add(key)
                sources.append({
                    "filename": result.source_filename,
                    "page_number": result.page_number,
                    "relevance_score": result.relevance_score,
                    "excerpt": (
                        result.text[:200] + "..."
                        if len(result.text) > 200
                        else result.text
                    ),
                })
        return sources