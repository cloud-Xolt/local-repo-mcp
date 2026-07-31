from pathlib import Path


def test_production_code_does_not_use_shell_true() -> None:
    root = Path(__file__).resolve().parents[1]
    files = list((root / "src").rglob("*.py")) + list((root / "gui").rglob("*.py"))
    offenders = [str(path.relative_to(root)) for path in files if "shell=True" in path.read_text(encoding="utf-8")]
    assert offenders == []
