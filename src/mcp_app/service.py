from __future__ import annotations

import os
import ssl
from pathlib import Path
from urllib.parse import urlsplit

from mcp.server import MCPServer

from audit.logger import AuditLogger
from mcp_app.http_policy import HttpSecurityMiddleware, HttpSecuritySettings
from mcp_app.version import VERSION
from tools.commits import register_commit_tools
from tools.patches import register_patch_tools
from tools.reads import register_read_tools
from tools.runtime import audit_event, build_context
from tools.tests import register_test_tools

mcp = MCPServer("Local Repo MCP", version=VERSION)
context = build_context(mcp)
register_read_tools(context)
register_patch_tools(context)
register_commit_tools(context)
register_test_tools(context)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "true" if default else "false").strip().lower()
    if raw not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise RuntimeError(f"{name} must be a boolean")
    return raw in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> list[str]:
    return [
        item.strip()
        for item in os.environ.get(name, "").split(",")
        if item.strip()
    ]


def _required_file(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value and not Path(value).expanduser().is_file():
        raise RuntimeError(f"{name} does not exist or is not a file: {value}")
    return value


def _validate_public_url(public_url: str, path: str) -> None:
    parsed = urlsplit(public_url)
    expected_path = path.rstrip("/") or "/"
    actual_path = parsed.path.rstrip("/") or "/"
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
        or actual_path != expected_path
    ):
        raise RuntimeError(
            "HTTP_PUBLIC_URL must be HTTPS, match HTTP_PATH, and contain "
            "no credentials, query, or fragment"
        )


def _run_http() -> None:
    host = os.environ.get("HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("HTTP_PORT", "8000"))
    except ValueError as exc:
        raise RuntimeError("HTTP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("HTTP_PORT must be between 1 and 65535")

    path = os.environ.get("HTTP_PATH", "/mcp").strip() or "/mcp"
    if not path.startswith("/"):
        path = "/" + path

    auth_mode = os.environ.get("HTTP_AUTH_MODE", "bearer").strip().lower()
    token = os.environ.get("HTTP_AUTH_TOKEN", "").strip()
    if auth_mode != "bearer":
        raise RuntimeError("Streamable HTTP requires bearer authentication")

    allowed_hosts = _csv_env("HTTP_ALLOWED_HOSTS")
    allowed_origins = _csv_env("HTTP_ALLOWED_ORIGINS")
    non_local = host.lower() not in {"127.0.0.1", "localhost", "::1"}
    if non_local and not allowed_hosts:
        raise RuntimeError("non-local HTTP binding requires HTTP_ALLOWED_HOSTS")

    certfile = _required_file("HTTP_TLS_CERTFILE")
    keyfile = _required_file("HTTP_TLS_KEYFILE")
    client_ca = _required_file("HTTP_TLS_CLIENT_CA")
    proxy_mode = _bool_env("HTTP_TLS_TERMINATED_PROXY", False)
    trusted_values = _csv_env("HTTP_PROXY_TRUSTED_IPS")
    public_url = os.environ.get("HTTP_PUBLIC_URL", "").strip()

    if bool(certfile) != bool(keyfile):
        raise RuntimeError(
            "HTTP_TLS_CERTFILE and HTTP_TLS_KEYFILE must be configured together"
        )
    if client_ca and not certfile:
        raise RuntimeError("HTTP_TLS_CLIENT_CA requires native TLS")
    if host in {"0.0.0.0", "::"} and not public_url:
        raise RuntimeError("wildcard HTTP binding requires HTTP_PUBLIC_URL")
    if public_url:
        _validate_public_url(public_url, path)
    if proxy_mode and not public_url:
        raise RuntimeError("TLS proxy mode requires HTTP_PUBLIC_URL")
    if non_local and not certfile and not proxy_mode:
        raise RuntimeError(
            "non-local HTTP binding requires native TLS or explicit "
            "TLS-terminated proxy mode"
        )

    security = HttpSecuritySettings.build(
        token=token,
        protected_path=path,
        proxy_mode=proxy_mode,
        trusted_values=trusted_values,
    )

    try:
        max_request_body_size = int(
            os.environ.get("HTTP_MAX_REQUEST_BYTES", "262144")
        )
    except ValueError as exc:
        raise RuntimeError("HTTP_MAX_REQUEST_BYTES must be an integer") from exc
    if not 1024 <= max_request_body_size <= 5_000_000:
        raise RuntimeError(
            "HTTP_MAX_REQUEST_BYTES must be between 1024 and 5000000"
        )

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

    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health(_request):
        return JSONResponse(
            {
                "status": "ok",
                "version": VERSION,
                "mode": context.mode,
                "repository": context.repo_root.name,
                "repository_hash": AuditLogger.hash_value(str(context.repo_root)),
            }
        )

    app.routes.append(Route("/healthz", health, methods=["GET"]))

    def audit_http(**record) -> None:
        client_host = str(record.pop("client_host", ""))
        audit_event(
            context,
            client_hash=(
                AuditLogger.hash_value(client_host) if client_host else ""
            ),
            **record,
        )

    app.add_middleware(
        HttpSecurityMiddleware,
        settings=security,
        audit=audit_http,
    )

    uvicorn_kwargs: dict = {
        "host": host,
        "port": port,
        "log_level": "info",
        "proxy_headers": proxy_mode,
        "forwarded_allow_ips": (
            ",".join(trusted_values) if proxy_mode else "127.0.0.1"
        ),
    }
    if certfile:
        uvicorn_kwargs.update(
            ssl_certfile=certfile,
            ssl_keyfile=keyfile,
        )
        if client_ca:
            uvicorn_kwargs.update(
                ssl_ca_certs=client_ca,
                ssl_cert_reqs=ssl.CERT_REQUIRED,
            )

    audit_event(
        context,
        event="http_listen",
        status="success",
        host=host,
        port=port,
        native_tls=bool(certfile),
        tls_proxy=proxy_mode,
    )
    import uvicorn

    uvicorn.run(app, **uvicorn_kwargs)


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    stop_status = "success"
    try:
        if transport == "stdio":
            mcp.run()
        elif transport == "streamable-http":
            _run_http()
        else:
            raise RuntimeError(
                "MCP_TRANSPORT must be stdio or streamable-http"
            )
    except Exception as exc:
        stop_status = "failed"
        audit_event(
            context,
            event="server_error",
            status="failed",
            error_type=type(exc).__name__,
        )
        raise
    finally:
        audit_event(context, event="server_stop", status=stop_status)


if __name__ == "__main__":
    main()
