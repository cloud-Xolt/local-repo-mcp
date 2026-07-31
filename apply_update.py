"""Remove legacy modules after copying this version over an existing checkout."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY_PATHS = (
    "src/session",
    "src/sandbox",
    "src/security/rbac.py",
    "src/security/risk.py",
    "src/security/policy_engine.py",
    "src/security/trust_boundary.py",
    "src/repo/branch.py",
    "src/tools/session.py",
    "config/policy.yaml",
    "gui/components_panel.py",
    "gui/local_registry.py",
    "tests/test_rbac.py",
    "tests/test_risk.py",
)


def main() -> None:
    removed: list[str] = []
    for relative in LEGACY_PATHS:
        target = ROOT / relative
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(relative + "/")
        elif target.exists():
            target.unlink()
            removed.append(relative)
    print("Removed legacy paths:")
    if removed:
        for item in removed:
            print(f"- {item}")
    else:
        print("- none found")


if __name__ == "__main__":
    main()
