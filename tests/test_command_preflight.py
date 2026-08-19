from __future__ import annotations

from pathlib import Path

from commands.models import CommandSpec
from commands.preflight import preflight_error


def test_python_preflight_accepts_project_markers(tmp_path: Path) -> None:
    spec = CommandSpec("python_pytest", "test", ("pytest",))
    project = tmp_path / "service"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='svc'\n", encoding="utf-8")

    assert preflight_error(spec, project) is None
    assert preflight_error(spec, tmp_path) is not None


def test_go_preflight_checks_go_mod(tmp_path: Path) -> None:
    spec = CommandSpec("go_test", "test", ("go", "test", "./..."))
    module = tmp_path / "backend"
    module.mkdir()
    (module / "go.mod").write_text("module example.com/backend\n\ngo 1.21\n", encoding="utf-8")

    assert preflight_error(spec, module) is None
    assert "go.mod" in (preflight_error(spec, tmp_path) or "")


def test_maven_preflight_checks_pom_xml(tmp_path: Path) -> None:
    spec = CommandSpec("maven_test", "test", ("mvn", "test"))
    module = tmp_path / "services" / "api"
    module.mkdir(parents=True)
    (module / "pom.xml").write_text("<project/>", encoding="utf-8")

    assert preflight_error(spec, module) is None
    assert "pom.xml" in (preflight_error(spec, tmp_path) or "")
