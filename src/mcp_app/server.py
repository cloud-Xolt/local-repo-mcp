from mcp.server.mcpserver import MCPServer

from tools.context import build_context
from tools.patch import register_patch_tools
from tools.read import register_read_tools
from tools.session import register_session_tools
from tools.test import register_test_tools

mcp = MCPServer("Local Repo MCP")
_ctx = build_context(mcp)

register_session_tools(_ctx)
register_read_tools(_ctx)
register_patch_tools(_ctx)
register_test_tools(_ctx)


def main() -> None:
    if not _ctx.repo_root.exists():
        raise RuntimeError(f"REPO_ROOT does not exist: {_ctx.repo_root}")
    mcp.run()


if __name__ == "__main__":
    main()
