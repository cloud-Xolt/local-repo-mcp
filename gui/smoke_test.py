from __future__ import annotations

import asyncio
import json
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


def _tool_payload(result: Any) -> dict[str, Any]:
    for attribute in ("structuredContent", "structured_content"):
        value = getattr(result, attribute, None)
        if isinstance(value, dict):
            return value
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


async def _exercise_session(session: Any, expected_root: Path) -> dict[str, Any]:
    await session.initialize()
    tools_result = await session.list_tools()
    names = sorted(tool.name for tool in tools_result.tools)
    missing = sorted(EXPECTED_TOOLS - set(names))
    if missing:
        raise RuntimeError("expected tools are missing: " + ", ".join(missing))

    status_result = await session.call_tool("repo_git_status", arguments={})
    if getattr(status_result, "isError", False) or getattr(
        status_result, "is_error", False
    ):
        raise RuntimeError("repo_git_status returned an MCP tool error")

    payload = _tool_payload(status_result)
    reported_root = str(payload.get("repository", {}).get("root", ""))
    if not reported_root:
        raise RuntimeError("repo_git_status did not report repository.root")
    if Path(reported_root).resolve() != expected_root.resolve():
        raise RuntimeError(
            "MCP repository mismatch: "
            f"configured={expected_root.resolve()} reported={reported_root}"
        )

    return {
        "tools": names,
        "tool_count": len(names),
        "repository_access": True,
        "configured_repository": str(expected_root.resolve()),
        "reported_repository": reported_root,
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
            result = await _exercise_session(session, Path(config.repo_root))
    return {"transport": "stdio", **result}


async def _test_http(config: AppConfig) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    try:
        import httpx2 as httpx
    except ImportError:
        import httpx  # type: ignore[no-redef]

    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {config.http_auth_token}"},
        follow_redirects=True,
    )
    try:
        async with streamable_http_client(
            config.endpoint_url(),
            http_client=http_client,
        ) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                result = await _exercise_session(session, Path(config.repo_root))
    finally:
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
