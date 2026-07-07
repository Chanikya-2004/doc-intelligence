# services/chunker.py

import logging
from dataclasses import dataclass, field
from typing import List

from .document_parser import ParsedDocument, PageContent

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """
    A single text chunk ready to be embedded.
    """
    chunk_id: int               # Sequential index
    text: str                   # The actual text
    source_filename: str        
    page_number: int            # Page where this chunk starts
    start_char: int             
    end_char: int               
    char_count: int = field(init=False)

    def __post_init__(self):
        self.char_count = len(self.text)


class SlidingWindowChunker:
    """
    Splits a ParsedDocument into overlapping TextChunks.
    Default: 1000 characters per chunk with 200 characters of overlap.
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size.")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.step = chunk_size - overlap 

    def chunk_document(self, parsed_doc: ParsedDocument) -> List[TextChunk]:
        if not parsed_doc.pages:
            return []

        # 1. Join all pages into one continuous string
        full_text, page_boundaries = self._build_full_text(parsed_doc)

        chunks: List[TextChunk] = []
        chunk_id = 0
        start = 0

        # 2. Apply sliding window
        while start < len(full_text):
            end = min(start + self.chunk_size, len(full_text))
            chunk_text = full_text[start:end].strip()

            if chunk_text:
                # Find which page this chunk belongs to
                page_number = self._find_page_number(start, page_boundaries)

                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    source_filename=parsed_doc.filename,
                    page_number=page_number,
                    start_char=start,
                    end_char=end,
                ))
                chunk_id += 1

            if end == len(full_text):
                break
            start += self.step

        return chunks

    def _build_full_text(self, parsed_doc: ParsedDocument):
        parts = []
        boundaries = []
        current_pos = 0
        for page in parsed_doc.pages:
            boundaries.append((current_pos, page.page_number))
            parts.append(page.text)
            current_pos += len(page.text) + 1
        return "\n".join(parts), boundaries

    def _find_page_number(self, char_offset, page_boundaries):
        page_number = 1
        for start_char, p_num in page_boundaries:
            if char_offset >= start_char:
                page_number = p_num
            else:
                break
        return page_number