from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from types import MappingProxyType

from commands.models import CommandSpec


def _gradle_executable() -> str:
    return "gradlew.bat" if os.name == "nt" else "./gradlew"


class CommandRegistry:
    """Read-only lookup for explicitly allowlisted repository commands."""

    def __init__(self, specs: Iterable[CommandSpec]) -> None:
        values: dict[str, CommandSpec] = {}
        for spec in specs:
            if not spec.key or spec.key in values:
                raise ValueError(f"duplicate or empty command key: {spec.key!r}")
            if not spec.argv:
                raise ValueError(f"command {spec.key!r} has empty argv")
            values[spec.key] = spec
        self._specs = MappingProxyType(values)

    def get(self, key: str) -> CommandSpec:
        normalized = str(key).strip()
        try:
            return self._specs[normalized]
        except KeyError as exc:
            allowed = ", ".join(sorted(self._specs))
            raise PermissionError(
                "repository command is not allowed: "
                f"{normalized!r}. command_key must be one allowlisted profile; "
                "use working_dir for project subdirectories inside the repository. "
                f"allowed={allowed}"
            ) from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))


DEFAULT_COMMAND_REGISTRY = CommandRegistry(
    (
        CommandSpec(
            "python_pytest",
            "test",
            (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"),
        ),
        CommandSpec("go_test", "test", ("go", "test", "./...")),
        CommandSpec("go_build", "build", ("go", "build", "./...")),
        CommandSpec("go_vet", "check", ("go", "vet", "./...")),
        CommandSpec("go_fmt", "check", ("go", "fmt", "./...")),
        CommandSpec("node_test", "test", ("npm", "test", "--")),
        CommandSpec("node_build", "build", ("npm", "run", "build", "--")),
        CommandSpec("node_lint", "lint", ("npm", "run", "lint", "--")),
        CommandSpec("maven_test", "test", ("mvn", "test")),
        CommandSpec(
            "maven_build", "build", ("mvn", "package", "-DskipTests")
        ),
        CommandSpec("gradle_test", "test", (_gradle_executable(), "test")),
        CommandSpec("gradle_build", "build", (_gradle_executable(), "build")),
    )
)
