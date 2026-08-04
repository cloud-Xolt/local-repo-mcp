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
        """Run an allowlisted repository test command.

        Supported keys are python_pytest, go_test, node_test, node_lint,
        maven_test, and gradle_test. Test mode grants access to this tool;
        the command key remains independently constrained by policy.
        """
        result = execute(
            context,
            tool="repo_run_test",
            modes=("test",),
            operation=lambda: context.test_runner.run(
                command_key,
                timeout_seconds,
            ),
            result_status=lambda value: (
                "success" if int(value.get("returncode", 1)) == 0 else "failed"
            ),
            command_key=command_key,
        )
        result["repository"] = repository_info(context)
        return result
