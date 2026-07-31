import subprocess

import pytest

from repo.git import reject_unsupported_patch_types, run_git
from security.scanner import SecretScanner
from tools.patch import ensure_clean_worktree


def _apply_via_git(repo_root, patch: str) -> None:
    result = run_git(repo_root, ["apply", "--whitespace=nowarn"], input_text=patch)
    assert result.returncode == 0, result.stderr


def test_reject_binary_patch(repo_root, runtime) -> None:
    patch = "GIT binary patch\n"
    with pytest.raises(PermissionError):
        reject_unsupported_patch_types(patch)


def test_reject_rename_patch(repo_root) -> None:
    patch = "rename from a\nrename to b\n"
    with pytest.raises(PermissionError):
        reject_unsupported_patch_types(patch)


def test_reject_symlink_patch(repo_root) -> None:
    patch = "new file mode 120000\n"
    with pytest.raises(PermissionError):
        reject_unsupported_patch_types(patch)


def test_reject_secret_in_patch(repo_root) -> None:
    patch = """--- a/src/app.py
+++ b/src/app.py
@@ -1 +1,2 @@
 print('hello')
+api_key = "super_secret_value_here"
"""
    scanner = SecretScanner()
    with pytest.raises(PermissionError):
        scanner.require_clean_patch(patch)


def test_reject_env_write(repo_root, runtime) -> None:
    patch = """--- /dev/null
+++ b/.env
@@ -0,0 +1 @@
+SECRET=1
"""
    with pytest.raises(Exception):
        runtime.git.patch_targets(patch)


def test_valid_patch_applies(repo_root, runtime) -> None:
    patch = """--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-print('hello')
+print('patched')
"""
    targets = runtime.git.patch_targets(patch)
    assert targets == ["src/app.py"]
    runtime.git.apply_patch_check(patch)
    runtime.git.apply_patch(patch)
    content = (repo_root / "src" / "app.py").read_text(encoding="utf-8")
    assert "patched" in content


def test_patch_does_not_commit(repo_root, runtime) -> None:
    patch = """--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-print('hello')
+print('patched2')
"""
    runtime.git.apply_patch(patch)
    result = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"], capture_output=True, text=True)
    assert "M src/app.py" in result.stdout or " M src/app.py" in result.stdout
    log = subprocess.run(["git", "-C", str(repo_root), "log", "-1", "--oneline"], capture_output=True, text=True)
    assert "init" in log.stdout
