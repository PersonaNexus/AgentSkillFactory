"""Extract API route — synchronous skill extraction."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(tags=["extract"])

_ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    model: str = Form("claude-sonnet-4-20250514"),
) -> dict:
    """Extract skills and role info from a job description file."""
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {suffix}")

    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Ingest
        from agentforge.cli import _ingest_file
        jd = _ingest_file(tmp_path)

        # Extract via LLM
        from agentforge.extraction.skill_extractor import SkillExtractor
        from agentforge.llm.client import LLMClient

        client = LLMClient(model=model)
        extractor = SkillExtractor(client=client)
        result = extractor.extract(jd)

        return json.loads(result.model_dump_json())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)
