from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from gui.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server.py"
EXPECTED_TOOLS = {
    "repo_list_files",
    "repo_read_file",
    "repo_search_code",
    "repo_git_status",
    "repo_git_diff",
}


async def _exercise_session(session: Any) -> dict[str, Any]:
    """Perform a real MCP handshake, discover tools, and call a safe tool."""
    await session.initialize()
    tools_result = await session.list_tools()
    names = sorted(tool.name for tool in tools_result.tools)
    missing = sorted(EXPECTED_TOOLS - set(names))
    if missing:
        raise RuntimeError(f"expected tools are missing: {', '.join(missing)}")

    status_result = await session.call_tool("repo_git_status", arguments={})
    if getattr(status_result, "isError", False) or getattr(status_result, "is_error", False):
        raise RuntimeError("repo_git_status returned an MCP tool error")

    return {
        "tools": names,
        "tool_count": len(names),
        "repository_access": True,
    }


async def _test_stdio(config: AppConfig) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    env.update(config.mcp_env())
    env["MCP_TRANSPORT"] = "stdio"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env=env,
        cwd=str(ROOT),
    )
    async with stdio_client(params) as streams:
        read_stream, write_stream = streams[:2]
        async with ClientSession(read_stream, write_stream) as session:
            result = await _exercise_session(session)
    return {"transport": "stdio", **result}


async def _test_http(config: AppConfig) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    http_client = None
    if config.http_auth_mode == "bearer":
        # MCP Python SDK v2 uses httpx2 when available. Keep a fallback for
        # environments that expose the compatible client as httpx.
        try:
            import httpx2 as httpx  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - compatibility fallback
            import httpx  # type: ignore[no-redef]
        http_client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {config.http_auth_token}"},
            follow_redirects=True,
        )

    try:
        kwargs = {"http_client": http_client} if http_client is not None else {}
        async with streamable_http_client(config.endpoint_url(), **kwargs) as streams:
            # SDK versions have returned either two streams or an additional
            # session-id callback. The MCP session needs only the first two.
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                result = await _exercise_session(session)
    finally:
        if http_client is not None:
            await http_client.aclose()

    return {
        "transport": "streamable-http",
        "endpoint": config.endpoint_url(),
        **result,
    }


def run_smoke_test(config: AppConfig) -> dict[str, Any]:
    if config.transport == "stdio":
        return asyncio.run(asyncio.wait_for(_test_stdio(config), timeout=45))
    return asyncio.run(asyncio.wait_for(_test_http(config), timeout=30))
