from __future__ import annotations

from typing import Any

from tools.execution import execute
from tools.runtime import RuntimeContext, repository_info


def register_test_tools(context: RuntimeContext) -> None:
    @context.mcp.tool()
    def repo_run_test(
        command_key: str,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        result = execute(
            context,
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: context.test_runner.run(
                command_key,
                timeout_seconds,
            ),
            command_key=command_key,
        )
        result["repository"] = repository_info(context)
        return result
