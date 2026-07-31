import subprocess
from pathlib import Path
from typing import Any

from security.trust_boundary import UNTRUSTED_NOTICE
from tools.context import RuntimeContext, audit_tool, require_global_permission, require_session


def register_read_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_list_files(path: str = ".", limit: int = 200, session_id: str = "") -> dict[str, Any]:
        f"""List files under repo root. {UNTRUSTED_NOTICE}"""
        require_global_permission(ctx, "read")
        if session_id:
            require_session(ctx, session_id, "read")

        result = ctx.filesystem.list_files(path, limit)
        audit_tool(ctx, "repo_list_files", session_id, {"path": path, "limit": limit}, "ok")
        return result

    @ctx.mcp.tool()
    def repo_read_file(path: str, session_id: str = "") -> dict[str, Any]:
        f"""Read file wrapped in untrusted_repository_content. {UNTRUSTED_NOTICE}"""
        require_global_permission(ctx, "read")
        if session_id:
            require_session(ctx, session_id, "read")

        result = ctx.filesystem.read_file(path)
        audit_tool(ctx, "repo_read_file", session_id, {"path": path}, "ok", targets=[path])
        return result

    @ctx.mcp.tool()
    def repo_search_code(query: str, limit: int = 50, session_id: str = "") -> dict[str, Any]:
        f"""Search code using ripgrep. {UNTRUSTED_NOTICE}"""
        require_global_permission(ctx, "read")
        if session_id:
            require_session(ctx, session_id, "read")

        ctx.filesystem.validate_search_query(query)

        cmd = [
            "rg",
            "--line-number",
            "--no-heading",
            "--hidden",
            "--glob",
            "!.git",
            "--glob",
            "!node_modules",
            "--glob",
            "!vendor",
            "--glob",
            "!.venv",
            query,
            str(ctx.repo_root),
        ]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=20, check=False)
        lines = []
        for line in result.stdout.splitlines()[:limit]:
            try:
                file_path, line_no, content = line.split(":", 2)
                rel = Path(file_path).resolve().relative_to(ctx.repo_root).as_posix()
                if ctx.policy.check_read(rel).allowed:
                    lines.append({"path": rel, "line": int(line_no), "text": content[:500]})
            except Exception:
                continue

        audit_tool(ctx, "repo_search_code", session_id, {"query": query, "limit": limit}, "ok")
        return {"matches": lines, "truncated": len(lines) >= limit, "untrusted": True}

    @ctx.mcp.tool()
    def repo_git_status(session_id: str = "") -> dict[str, Any]:
        """Return git status."""
        require_global_permission(ctx, "read")
        if session_id:
            require_session(ctx, session_id, "read")

        audit_tool(ctx, "repo_git_status", session_id, {}, "ok")
        return {"status": ctx.git.status_short(), "branch": ctx.git.current_branch()}

    @ctx.mcp.tool()
    def repo_git_diff(staged: bool = False, max_bytes: int = 200000, session_id: str = "") -> dict[str, Any]:
        """Return git diff."""
        require_global_permission(ctx, "read")
        if session_id:
            require_session(ctx, session_id, "read")

        diff = ctx.git.diff(staged=staged)
        truncated = False
        if len(diff.encode("utf-8")) > max_bytes:
            diff = diff[:max_bytes]
            truncated = True

        audit_tool(ctx, "repo_git_diff", session_id, {"staged": staged}, "ok")
        return {"diff": diff, "truncated": truncated, "branch": ctx.git.current_branch()}
