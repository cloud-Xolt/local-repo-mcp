import pytest

from tools.read import build_ripgrep_command


@pytest.mark.parametrize(
    "query",
    [
        "--files",
        "--pre=touch /tmp/pwn",
        "-g",
        "--hidden",
    ],
)
def test_search_query_passed_as_fixed_string_argument(query: str) -> None:
    cmd = build_ripgrep_command(query)
    assert cmd.count("-e") == 1
    assert cmd[cmd.index("-e") + 1] == query
    assert "--fixed-strings" in cmd
    assert "--" in cmd
    assert cmd[-1] == "."


def test_search_query_length_validation() -> None:
    from tools.read import register_read_tools
    from mcp.server.mcpserver import MCPServer
    from tools.context import build_context
    import os
    from pathlib import Path

    os.environ.setdefault("REPO_ROOT", str(Path(".").resolve()))
    os.environ.setdefault("MCP_MODE", "read")
    ctx = build_context(MCPServer("test"))
    register_read_tools(ctx)
    tool = None
    for item in ctx.mcp._tool_manager._tools.values():  # type: ignore[attr-defined]
        if item.name == "repo_search_code":
            tool = item.fn
            break
    assert tool is not None
    with pytest.raises(ValueError):
        tool(query="")
    with pytest.raises(ValueError):
        tool(query="x" * 201)
