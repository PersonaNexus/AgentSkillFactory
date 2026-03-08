"""Tests for document ingestion modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentforge.ingestion.text import _detect_sections, _extract_title, ingest_file, ingest_text
from agentforge.models.job_description import JDSource


class TestTextIngestion:
    def test_ingest_plain_text(self):
        text = """Senior Software Engineer

About the Role:
We are looking for a senior engineer to lead our platform team.

Requirements:
- 5+ years Python experience
- Strong system design skills
"""
        jd = ingest_text(text)
        assert jd.title == "Senior Software Engineer"
        assert jd.source == JDSource.TEXT
        assert len(jd.sections) > 0

    def test_ingest_with_explicit_title(self):
        jd = ingest_text("Some job description text here.", title="Custom Title")
        assert jd.title == "Custom Title"

    def test_ingest_with_company(self):
        jd = ingest_text("A job at Acme with description.", company="Acme Corp")
        assert jd.company == "Acme Corp"

    def test_ingest_markdown_headings(self):
        text = """# Product Manager

## Responsibilities
- Define product roadmap
- Work with engineering

## Requirements
- 3+ years PM experience
- Strong analytical skills
"""
        jd = ingest_text(text)
        assert jd.title == "Product Manager"
        sections = jd.section_map
        assert "Responsibilities" in sections
        assert "Requirements" in sections

    def test_detect_sections_colon_headings(self):
        text = """Responsibilities:
Build things and do stuff.

Qualifications:
Have skills and experience.
"""
        sections = _detect_sections(text)
        headings = [s.heading for s in sections]
        assert "Responsibilities" in headings
        assert "Qualifications" in headings

    def test_extract_title_from_first_line(self):
        assert _extract_title("Data Analyst\nSome content") == "Data Analyst"

    def test_extract_title_strips_markdown(self):
        assert _extract_title("# Senior DevOps Engineer\nContent") == "Senior DevOps Engineer"

    def test_extract_title_fallback(self):
        assert _extract_title("\n\n\n") == "Untitled Position"


class TestFileIngestion:
    def test_ingest_text_file(self, fixtures_dir):
        jd = ingest_file(fixtures_dir / "senior_data_engineer.txt")
        assert jd.source == JDSource.FILE
        assert "data" in jd.title.lower() or "engineer" in jd.title.lower()
        assert jd.metadata["file_path"]
        assert len(jd.sections) > 0

    def test_ingest_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            ingest_file("/nonexistent/path/file.txt")

    def test_all_fixture_files(self, fixtures_dir):
        for txt_file in fixtures_dir.glob("*.txt"):
            jd = ingest_file(txt_file)
            assert jd.title
            assert jd.raw_text
            assert len(jd.raw_text) > 50
