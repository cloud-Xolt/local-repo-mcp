from typing import Any

from tools.context import RuntimeContext, audit_tool, require_global_permission, require_mode, require_session


def register_session_tools(ctx: RuntimeContext) -> None:
    @ctx.mcp.tool()
    def repo_session_start(user: str, permission: str = "write") -> dict[str, Any]:
        """Start agent session and switch to agent/{session_id} branch. Required before write/test."""
        require_mode(ctx, "write", "test", "ship")
        required = permission if permission != "execute" else "test"
        require_global_permission(ctx, required)

        if permission not in ("read", "write", "test", "execute", "ship"):
            raise ValueError("permission must be read/write/test/execute/ship")

        role_decision = ctx.rbac.require_permission(user, required)
        branch = ctx.git.ensure_agent_branch(f"pending-{user}")
        session = ctx.sessions.create(
            user=user,
            permission=permission,
            branch=branch,
            role=role_decision.role,
        )
        branch = ctx.git.ensure_agent_branch(session.session_id)
        ctx.sessions.update_branch(session.session_id, branch)

        audit_tool(
            ctx,
            "repo_session_start",
            session.session_id,
            {"user": user, "permission": permission, "role": role_decision.role},
            "ok",
            user=user,
        )

        return {
            "session_id": session.session_id,
            "user": session.user,
            "role": session.role,
            "branch": branch,
            "permission": session.permission,
            "repo_root": str(ctx.repo_root),
        }

    @ctx.mcp.tool()
    def repo_session_end(session_id: str) -> dict[str, Any]:
        """End an agent session."""
        ctx.sessions.require(session_id, "read")
        ctx.sessions.end(session_id)
        audit_tool(ctx, "repo_session_end", session_id, {}, "ok")
        return {"ended": True, "session_id": session_id}
