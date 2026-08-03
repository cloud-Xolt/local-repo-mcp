from __future__ import annotations

import hmac
import os
import subprocess

from mcp.server import MCPServer

from tools.context import build_context
from tools.patch import register_patch_tools
from tools.read import register_read_tools
from tools.test import register_test_tools

mcp = MCPServer("Local Repo MCP", version="1.2.1")
_ctx = build_context(mcp)
register_read_tools(_ctx)
register_patch_tools(_ctx)
register_test_tools(_ctx)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def _validate_repo() -> None:
    if not _ctx.repo_root.exists():
        raise RuntimeError(f"REPO_ROOT does not exist: {_ctx.repo_root}")
    if not _ctx.repo_root.is_dir():
        raise RuntimeError(f"REPO_ROOT is not a directory: {_ctx.repo_root}")
    try:
        result = subprocess.run(
            ["git", "-C", str(_ctx.repo_root), "rev-parse", "--is-inside-work-tree"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except OSError as exc:
        raise RuntimeError("Git is required but was not found") from exc
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(f"REPO_ROOT is not a Git working tree: {_ctx.repo_root}")


def _run_http() -> None:
    host = os.environ.get("HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("HTTP_PORT", "8000"))
    if not 1 <= port <= 65535:
        raise RuntimeError("HTTP_PORT must be between 1 and 65535")

    path = os.environ.get("HTTP_PATH", "/mcp").strip() or "/mcp"
    if not path.startswith("/"):
        path = "/" + path

    token = os.environ.get("HTTP_AUTH_TOKEN", "").strip()
    auth_mode = os.environ.get("HTTP_AUTH_MODE", "bearer").strip().lower()
    allowed_hosts = _csv_env("HTTP_ALLOWED_HOSTS")
    allowed_origins = _csv_env("HTTP_ALLOWED_ORIGINS")
    non_local = host not in {"127.0.0.1", "localhost", "::1"}

    if auth_mode != "bearer":
        raise RuntimeError("Streamable HTTP requires bearer authentication")
    if not token:
        raise RuntimeError("HTTP_AUTH_MODE=bearer requires HTTP_AUTH_TOKEN")
    if non_local and not allowed_hosts:
        raise RuntimeError("non-local HTTP binding requires HTTP_ALLOWED_HOSTS")

    max_request_body_size = int(os.environ.get("HTTP_MAX_REQUEST_BYTES", "262144"))
    if not 1024 <= max_request_body_size <= 5_000_000:
        raise RuntimeError("HTTP_MAX_REQUEST_BYTES must be between 1024 and 5000000")

    kwargs: dict = {
        "streamable_http_path": path,
        "json_response": _bool_env("HTTP_JSON_RESPONSE", True),
        "stateless_http": _bool_env("HTTP_STATELESS", True),
        "max_request_body_size": max_request_body_size,
        "host": host,
    }
    if allowed_hosts or allowed_origins:
        from mcp.server.transport_security import TransportSecuritySettings
        kwargs["transport_security"] = TransportSecuritySettings(
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )

    app = mcp.streamable_http_app(**kwargs)

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            base_path = path.rstrip("/") or "/"
            request_path = request.url.path
            protected = (
                base_path == "/"
                or request_path == base_path
                or request_path.startswith(base_path + "/")
            )
            if protected:
                expected = f"Bearer {token}"
                supplied = request.headers.get("authorization", "")
                if not hmac.compare_digest(supplied, expected):
                    return JSONResponse(
                        {"error": "unauthorized"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            return await call_next(request)

    app.add_middleware(BearerAuthMiddleware)

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    _validate_repo()
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
    elif transport in {"streamable-http", "http"}:
        _run_http()
    else:
        raise RuntimeError("MCP_TRANSPORT must be stdio or streamable-http")


if __name__ == "__main__":
    main()
