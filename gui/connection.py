from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from gui.config import AppConfig
from gui.runtime_config import environment_for
from mcp_app.runtime import launcher_command

ROOT = Path(__file__).resolve().parents[1]
LogCallback = Callable[[str], None] | None


def _emit(callback: LogCallback, message: str) -> None:
    if callback is not None:
        callback(message)


def _result_payload(result: Any) -> dict[str, Any]:
    for name in ("structuredContent", "structured_content"):
        value = getattr(result, name, None)
        if isinstance(value, dict):
            return value
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError("MCP tool response did not contain a structured object")


async def _exercise_session(
    session: Any,
    expected_repository: Path,
    callback: LogCallback,
) -> dict[str, Any]:
    _emit(callback, "Initializing MCP session")
    await session.initialize()
    _emit(callback, "MCP initialize completed")

    listed = await session.list_tools()
    tools = [tool.name for tool in getattr(listed, "tools", [])]
    if "repo_git_status" not in tools:
        raise RuntimeError("repo_git_status was not exposed by the MCP server")
    _emit(callback, f"Discovered {len(tools)} MCP tools")

    _emit(callback, "Checking repository identity with repo_git_status")
    result = await session.call_tool("repo_git_status", {})
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        raise RuntimeError("repo_git_status returned an MCP tool error")
    payload = _result_payload(result)
    repository = payload.get("repository")
    actual_root = repository.get("root") if isinstance(repository, dict) else repository
    if not isinstance(actual_root, str) or not actual_root.strip():
        raise RuntimeError("repo_git_status did not report the repository root")
    expected = expected_repository.expanduser().resolve()
    actual = Path(actual_root).expanduser().resolve()
    if actual != expected:
        raise RuntimeError(
            f"MCP repository mismatch: configured={expected}, connected={actual}"
        )
    _emit(callback, f"Repository verified: {actual}")
    return {
        "tools": tools,
        "repository": repository,
        "git_status": payload,
    }


async def _test_stdio(
    config: AppConfig,
    callback: LogCallback = None,
) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = launcher_command()
    environment = os.environ.copy()
    environment.update(environment_for(config))
    environment["MCP_TRANSPORT"] = "stdio"
    parameters = StdioServerParameters(
        command=command[0],
        args=command[1:],
        env=environment,
        cwd=str(ROOT),
    )
    _emit(callback, "Starting temporary STDIO MCP connection")
    try:
        async with stdio_client(parameters) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                result = await _exercise_session(
                    session,
                    Path(config.repo_root),
                    callback,
                )
        _emit(callback, "STDIO MCP connection completed")
        return {"transport": "stdio", **result}
    except Exception as exc:
        _emit(callback, f"STDIO MCP connection failed: {type(exc).__name__}: {exc}")
        raise
    finally:
        _emit(callback, "Temporary STDIO MCP connection closed")


async def _test_http(
    config: AppConfig,
    callback: LogCallback = None,
) -> dict[str, Any]:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    endpoint = config.endpoint_url()
    _emit(callback, f"Connecting to HTTP MCP endpoint: {endpoint}")
    parsed = urlsplit(endpoint)
    verify: bool | str = True
    if (
        parsed.scheme == "https"
        and not config.http_public_url.strip()
        and config.http_tls_certfile.strip()
    ):
        verify = config.http_tls_certfile

    kwargs: dict[str, Any] = {
        "headers": {"Authorization": f"Bearer {config.http_auth_token}"},
        "follow_redirects": False,
        "verify": verify,
    }
    if config.http_client_certfile.strip() and config.http_client_keyfile.strip():
        kwargs["cert"] = (
            config.http_client_certfile,
            config.http_client_keyfile,
        )

    client = httpx.AsyncClient(**kwargs)
    try:
        async with streamable_http_client(endpoint, http_client=client) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                result = await _exercise_session(
                    session,
                    Path(config.repo_root),
                    callback,
                )
        _emit(callback, "HTTP MCP connection completed")
        return {
            "transport": "streamable-http",
            "endpoint": endpoint,
            **result,
        }
    except Exception as exc:
        _emit(callback, f"HTTP MCP connection failed: {type(exc).__name__}: {exc}")
        raise
    finally:
        await client.aclose()
        _emit(callback, "HTTP MCP client closed")


def run_connection_test(
    config: AppConfig,
    log_callback: LogCallback = None,
) -> dict[str, Any]:
    if config.transport == "stdio":
        return asyncio.run(
            asyncio.wait_for(_test_stdio(config, log_callback), timeout=45)
        )
    return asyncio.run(
        asyncio.wait_for(_test_http(config, log_callback), timeout=30)
    )
