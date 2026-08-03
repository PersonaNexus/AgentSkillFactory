"""Bearer token authentication middleware for the AgentForge web API.

Configure via:
  - Environment variable: AGENTFORGE_API_TOKEN
  - Config file: ~/.agentforge/config.yaml -> web_api_token

Set AGENTFORGE_API_TOKEN=disabled to explicitly disable auth (local dev only).

When binding to a non-loopback address (e.g. 0.0.0.0), a token is required
unless auth is explicitly disabled. Local loopback (127.0.0.1 / ::1) remains
open when no token is set for convenience.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

try:  # Optional web extras are not required for core imports/tests.
    from fastapi import HTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
except ModuleNotFoundError:  # pragma: no cover - exercised by core-only installs
    BaseHTTPMiddleware = object  # type: ignore[misc,assignment,unused-ignore]

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    Request = Any  # type: ignore[misc,assignment,unused-ignore]
    Response = Any  # type: ignore[misc,assignment,unused-ignore]

logger = logging.getLogger(__name__)

# Explicit opt-out sentinel (not a real secret).
_AUTH_DISABLED = "disabled"

# Paths that never require auth
_PUBLIC_PATHS = frozenset({"/", "/health"})
_PUBLIC_PREFIXES = ("/static/", "/api/docs", "/openapi.json")

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"})


def _get_api_token() -> str | None:
    """Resolve the API token from env or config.

    Returns None if no token is configured (auth disabled for loopback).
    Returns "disabled" if explicitly opted out.
    """
    env_token = os.environ.get("AGENTFORGE_API_TOKEN", "").strip()
    if env_token:
        return env_token

    # Fall back to config file
    try:
        from agentforge.config import load_config

        config = load_config()
        return getattr(config, "web_api_token", None) or None
    except Exception:
        return None


def is_loopback_host(host: str) -> bool:
    """Return True if *host* is a loopback bind address."""
    return host.strip().lower() in _LOOPBACK_HOSTS


def auth_status() -> tuple[str, str | None]:
    """Return (mode, token_or_none).

    mode is one of: "required", "disabled", "open" (loopback convenience).
    """
    token = _get_api_token()
    if token == _AUTH_DISABLED:
        return "disabled", None
    if token:
        return "required", token
    return "open", None


def ensure_bind_auth(host: str) -> None:
    """Raise ValueError if binding *host* without auth is unsafe.

    Non-loopback binds require AGENTFORGE_API_TOKEN (or explicit 'disabled').
    """
    if is_loopback_host(host):
        return
    mode, _ = auth_status()
    if mode == "open":
        raise ValueError(
            f"Refusing to bind to {host!r} without API authentication.\n"
            "Set AGENTFORGE_API_TOKEN to a secret, or set it to 'disabled' "
            "to explicitly opt out (not recommended on public interfaces).\n"
            "Example: export AGENTFORGE_API_TOKEN=$(openssl rand -hex 32)"
        )


class BearerAuthMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Validates Bearer token on API routes.

    - Token set → require matching Bearer header on /api/* routes.
    - Token == 'disabled' → allow all (explicit opt-out).
    - No token → allow all (intended for local loopback; bind check enforces
      non-loopback safety at serve time).
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip auth for public paths
        path = request.url.path
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Skip auth for page routes (HTML pages served by the SPA)
        if not path.startswith("/api/"):
            return await call_next(request)

        token = _get_api_token()

        # No token configured or explicitly disabled → allow all
        if not token or token == _AUTH_DISABLED:
            return await call_next(request)

        # Validate Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        provided = auth_header[len("Bearer "):]
        if not hmac.compare_digest(provided, token):
            raise HTTPException(status_code=403, detail="Invalid API token")

        return await call_next(request)
