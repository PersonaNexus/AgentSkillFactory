"""FastAPI application factory for the AgentForge web UI."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agentforge import __version__
from agentforge.web.jobs import JobStore

_WEB_DIR = Path(__file__).parent
_STATIC_DIR = _WEB_DIR / "static"
_TEMPLATES_DIR = _WEB_DIR / "templates"


def _start_cleanup_thread(store: JobStore) -> None:
    """Periodically clean up expired jobs."""

    def _loop() -> None:
        while True:
            time.sleep(300)
            store.cleanup()

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentForge",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )

    store = JobStore()
    app.state.jobs = store
    _start_cleanup_thread(store)

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register route modules
    from agentforge.web.routes import batch, culture, extract, forge, pages, settings

    app.include_router(pages.router)
    app.include_router(extract.router, prefix="/api")
    app.include_router(forge.router, prefix="/api")
    app.include_router(batch.router, prefix="/api")
    app.include_router(culture.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")

    return app
