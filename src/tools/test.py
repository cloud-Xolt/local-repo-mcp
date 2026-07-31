from typing import Any

from tools.context import RuntimeContext, audit_tool, require_global_permission, require_mode, require_session


def register_test_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_run_test(command_key: str, session_id: str, timeout_seconds: int = 120) -> dict[str, Any]:
        """Run whitelisted test in Docker sandbox (network disabled, read-only mount)."""
        require_mode(ctx, "test", "ship")
        require_global_permission(ctx, "test")
        session = require_session(ctx, session_id, "test")
        ctx.rbac.require_permission(session.user, "test")

        decision = ctx.policy.check_execute(command_key)
        if not decision.allowed:
            raise PermissionError(decision.reason)

        timeout_seconds = min(max(timeout_seconds, 1), ctx.test_timeout_max)
        assessment = ctx.risk.assess(
            "repo_run_test",
            user=session.user,
            branch=ctx.git.current_branch(),
        )
        ctx.risk.require_acceptable(assessment)

        result = ctx.sandbox.run_test(command_key, timeout_seconds)

        audit_tool(
            ctx,
            "repo_run_test",
            session_id,
            {"command_key": command_key, "timeout_seconds": timeout_seconds},
            f"exit={result['returncode']}",
            user=session.user,
        )
        return result
