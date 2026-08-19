from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from commands.models import CommandSpec


@dataclass(frozen=True)
class PreflightRule:
    prefix: str
    marker: str
    check: Callable[[Path], bool]


def _python_project(root: Path) -> bool:
    if any(
        (root / name).is_file()
        for name in ("pyproject.toml", "pytest.ini", "setup.py", "setup.cfg", "tox.ini")
    ):
        return True
    tests = root / "tests"
    return tests.is_dir() and any(tests.glob("test_*.py"))


def _gradle_project(root: Path) -> bool:
    return any(
        (root / name).is_file()
        for name in (
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        )
    )


PREFLIGHT_RULES: tuple[PreflightRule, ...] = (
    PreflightRule("python_", "Python project markers", _python_project),
    PreflightRule("go_", "go.mod", lambda root: (root / "go.mod").is_file()),
    PreflightRule("node_", "package.json", lambda root: (root / "package.json").is_file()),
    PreflightRule("maven_", "pom.xml", lambda root: (root / "pom.xml").is_file()),
    PreflightRule("gradle_", "Gradle build files", _gradle_project),
)


def preflight_error(spec: CommandSpec, working_dir: Path) -> str | None:
    for rule in PREFLIGHT_RULES:
        if not spec.key.startswith(rule.prefix):
            continue
        if rule.check(working_dir):
            return None
        return (
            f"working_dir {working_dir} is missing required {rule.marker}; "
            "set working_dir to the language project root inside the repository"
        )
    return None
