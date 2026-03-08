"""Plain text and markdown job description ingestion."""

from __future__ import annotations

import re
from pathlib import Path

from agentforge.models.job_description import JDSection, JDSource, JobDescription


def _detect_sections(text: str) -> list[JDSection]:
    """Detect sections in text by common heading patterns."""
    section_pattern = re.compile(
        r"^(?:#{1,3}\s+|[A-Z][A-Za-z\s/&]+:\s*$|[A-Z][A-Za-z\s/&]+\n[-=]+)",
        re.MULTILINE,
    )

    # Common JD section headings
    heading_keywords = [
        "responsibilities", "duties", "requirements", "qualifications",
        "skills", "experience", "education", "about", "description",
        "overview", "summary", "benefits", "compensation", "what you",
        "who you", "role", "position", "job", "preferred", "nice to have",
    ]

    sections: list[JDSection] = []
    lines = text.split("\n")
    current_heading = "Overview"
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()
        is_heading = False

        # Check for markdown headings
        if stripped.startswith("#"):
            is_heading = True
            heading_text = stripped.lstrip("#").strip()
        # Check for colon-terminated headings
        elif stripped.endswith(":") and len(stripped) < 60:
            lower = stripped.lower().rstrip(":")
            if any(kw in lower for kw in heading_keywords):
                is_heading = True
                heading_text = stripped.rstrip(":")
        # Check for all-caps headings
        elif stripped.isupper() and 3 < len(stripped) < 60:
            is_heading = True
            heading_text = stripped.title()

        if is_heading:
            if current_content:
                content = "\n".join(current_content).strip()
                if content:
                    sections.append(JDSection(heading=current_heading, content=content))
            current_heading = heading_text
            current_content = []
        else:
            current_content.append(line)

    # Capture final section
    if current_content:
        content = "\n".join(current_content).strip()
        if content:
            sections.append(JDSection(heading=current_heading, content=content))

    return sections


def _extract_title(text: str) -> str:
    """Try to extract a job title from the text."""
    lines = text.strip().split("\n")
    for line in lines[:5]:
        stripped = line.strip().lstrip("#").strip()
        if stripped and len(stripped) < 100:
            return stripped
    return "Untitled Position"


def ingest_text(text: str, title: str | None = None, company: str | None = None) -> JobDescription:
    """Ingest a plain text or markdown job description."""
    sections = _detect_sections(text)
    return JobDescription(
        source=JDSource.TEXT,
        title=title or _extract_title(text),
        company=company,
        raw_text=text,
        sections=sections,
    )


def ingest_file(path: str | Path, company: str | None = None) -> JobDescription:
    """Ingest a job description from a text/markdown file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fall back to latin-1 which can decode any byte sequence
        text = file_path.read_text(encoding="latin-1")

    jd = ingest_text(text, company=company)
    jd.source = JDSource.FILE
    jd.metadata["file_path"] = str(file_path.resolve())
    return jd
