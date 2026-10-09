"""Streamable-HTTP MCP app with optional Bearer token auth (Tailscale/LAN)."""

from __future__ import annotations

import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pen_agent.config import Settings
from pen_agent.server import build_mcp


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/"}:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        q = request.query_params.get("token", "")
        ok = False
        if auth.lower().startswith("bearer ") and auth.split(" ", 1)[1].strip() == self.token:
            ok = True
        if q and q == self.token:
            ok = True
        if not ok:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def create_app(settings: Optional[Settings] = None):
    """Return ASGI app for uvicorn: pen_agent.http_app:create_app."""
    settings = settings or Settings.from_env()
    mcp = build_mcp(settings)

    # Prefer streamable HTTP app from FastMCP
    app = None
    for attr in ("streamable_http_app", "sse_app", "app"):
        if hasattr(mcp, attr):
            maybe = getattr(mcp, attr)
            app = maybe() if callable(maybe) else maybe
            if app is not None:
                break
    if app is None:
        raise RuntimeError(
            "This mcp FastMCP build has no HTTP app. "
            "Upgrade mcp or use --transport stdio."
        )

    # Health route
    async def health(_request: Request) -> Response:
        return JSONResponse(
            {
                "ok": True,
                "service": "pen-agent",
                "profile": settings.profile,
                "auth": bool(settings.auth_token),
            }
        )

    try:
        from starlette.routing import Route

        app.routes.insert(0, Route("/health", health))
    except Exception:
        pass

    token = settings.auth_token or os.environ.get("PEN_AGENT_TOKEN", "")
    if token:
        app = BearerAuthMiddleware(app, token)
    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.http_host,
        port=settings.http_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
