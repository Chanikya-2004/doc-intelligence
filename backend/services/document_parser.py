# services/document_parser.py

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Configure module-level logger — use the root app logger in production
logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """
    Represents the extracted text from a single PDF page.
    The dataclass gives us a clean, type-safe container with no boilerplate.
    """
    page_number: int          # 1-indexed (human-readable)
    text: str                 # Raw extracted text for this page
    char_count: int = field(init=False)

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ParsedDocument:
    """
    The full result of parsing a PDF: all pages + top-level metadata.
    """
    filename: str
    total_pages: int
    pages: List[PageContent]
    total_characters: int = field(init=False)

    def __post_init__(self):
        self.total_characters = sum(p.char_count for p in self.pages)

    @property
    def full_text(self) -> str:
        """Convenience: join all pages into one string (for debugging)."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


class DocumentParser:
    """
    Handles PDF → structured text extraction.

    Design principles:
    - Stateless: no instance variables mutated during parse.
    - Raises descriptive exceptions so the caller (main.py) can return
      meaningful HTTP error responses.
    """

    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a PDF file and return a structured ParsedDocument.

        Args:
            file_path: Absolute or relative path to the .pdf file.

        Returns:
            ParsedDocument with per-page text and metadata.

        Raises:
            FileNotFoundError: If the file does not exist at the given path.
            ValueError: If the file is not a valid PDF, is encrypted, or has
                        no extractable text (e.g., a scanned image-only PDF).
            RuntimeError: For unexpected pypdf errors.
        """
        file_path = Path(file_path)

        # --- Guard 1: File existence ---
        if not file_path.exists():
            raise FileNotFoundError(
                f"PDF not found at path: {file_path}. "
                "Check that the file was saved correctly after upload."
            )

        # --- Guard 2: File extension ---
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(
                f"Expected a .pdf file, got '{file_path.suffix}'. "
                "Only PDF files are supported."
            )

        logger.info("Parsing PDF: %s", file_path.name)

        try:
            reader = PdfReader(str(file_path))
        except PdfReadError as e:
            raise ValueError(
                f"Could not read '{file_path.name}' as a PDF. "
                f"The file may be corrupted or not a valid PDF. Detail: {e}"
            ) from e

        # --- Guard 3: Encrypted PDFs ---
        if reader.is_encrypted:
            raise ValueError(
                f"'{file_path.name}' is password-protected. "
                "Please provide an unencrypted PDF."
            )

        # --- Guard 4: Empty PDF ---
        if len(reader.pages) == 0:
            raise ValueError(
                f"'{file_path.name}' has 0 pages. The PDF appears to be empty."
            )

        # --- Core extraction loop ---
        pages: List[PageContent] = []
        for i, page in enumerate(reader.pages):
            raw_text = page.extract_text() or ""
            # Normalize whitespace: collapse multiple spaces/newlines
            cleaned_text = " ".join(raw_text.split())

            pages.append(PageContent(
                page_number=i + 1,   # Convert 0-indexed to 1-indexed
                text=cleaned_text,
            ))
            logger.debug("  Page %d: %d chars extracted", i + 1, len(cleaned_text))

        # --- Guard 5: Image-only / scanned PDF ---
        total_chars = sum(p.char_count for p in pages)
        if total_chars < 50:
            raise ValueError(
                f"'{file_path.name}' appears to be a scanned or image-only PDF. "
                f"Only {total_chars} characters were extracted across "
                f"{len(reader.pages)} pages. "
                "Use an OCR tool (e.g., pytesseract) to pre-process it."
            )

        result = ParsedDocument(
            filename=file_path.name,
            total_pages=len(reader.pages),
            pages=pages,
        )

        logger.info(
            "Parsed '%s': %d pages, %d total characters",
            result.filename, result.total_pages, result.total_characters
        )
        return result