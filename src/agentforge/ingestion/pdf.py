"""PDF job description ingestion using pymupdf."""

from __future__ import annotations

from pathlib import Path

from agentforge.ingestion.text import ingest_text
from agentforge.models.job_description import JDSource, JobDescription

_MAX_PDF_SIZE_MB = 50


def ingest_pdf(path: str | Path, company: str | None = None) -> JobDescription:
    """Extract text from a PDF file and ingest as a job description."""
    import fitz  # pymupdf

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Check file size
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > _MAX_PDF_SIZE_MB:
        raise ValueError(
            f"PDF file too large ({size_mb:.1f}MB). "
            f"Maximum supported size is {_MAX_PDF_SIZE_MB}MB."
        )

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise ValueError(f"Failed to open PDF file: {path}. File may be corrupted.") from e

    pages: list[str] = []
    try:
        for page in doc:
            pages.append(page.get_text())
    finally:
        doc.close()

    full_text = "\n\n".join(pages)
    if not full_text.strip():
        raise ValueError(f"No text content extracted from PDF: {path}")

    jd = ingest_text(full_text, company=company)
    jd.source = JDSource.FILE
    jd.metadata["file_path"] = str(file_path.resolve())
    jd.metadata["format"] = "pdf"
    jd.metadata["page_count"] = len(pages)
    return jd
