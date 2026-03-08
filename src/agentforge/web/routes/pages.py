"""Page routes — SPA shell and health check."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from agentforge import __version__

router = APIRouter()
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the SPA shell."""
    html = (_TEMPLATES_DIR / "index.html").read_text()
    return HTMLResponse(html)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}
