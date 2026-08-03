from __future__ import annotations

from typing import Any

from tools.context import RuntimeContext, audit_event, repository_info, require_mode


def register_test_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_run_test(command_key: str, timeout_seconds: int = 120) -> dict[str, Any]:
        require_mode(ctx, "test")
        result = ctx.test_runner.run(command_key, timeout_seconds)
        audit_event(
            ctx,
            tool="repo_run_test",
            status="success" if result["returncode"] == 0 else "failed",
        )
        result["repository"] = repository_info(ctx)
        return result
