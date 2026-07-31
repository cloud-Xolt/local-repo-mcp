import subprocess

from repo.git import GitController, run_git


def _track_env(repo_root) -> None:
    subprocess.run(["git", "add", ".env"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "track env"], cwd=repo_root, check=True)


def test_git_status_hides_env(repo_root) -> None:
    _track_env(repo_root)
    (repo_root / ".env").write_text("SECRET=2\n", encoding="utf-8")
    git = GitController(repo_root, lambda *a, **k: run_git(repo_root, *a, **k), 200000)
    status = git.status_filtered()
    paths = [entry["path"] for entry in status["entries"]]
    assert ".env" not in paths
    assert status["hidden_entries"] >= 1


def test_git_diff_hides_sensitive(repo_root) -> None:
    _track_env(repo_root)
    env_path = repo_root / ".env"
    env_path.write_text("SECRET=changed\n", encoding="utf-8")
    git = GitController(repo_root, lambda *a, **k: run_git(repo_root, *a, **k), 200000)
    diff = git.diff_filtered(staged=False)
    assert ".env" not in diff["diff"]
    assert diff["hidden_files"] >= 1


def test_git_diff_allows_normal_file(repo_root) -> None:
    app = repo_root / "src" / "app.py"
    app.write_text("print('changed')\n", encoding="utf-8")
    git = GitController(repo_root, lambda *a, **k: run_git(repo_root, *a, **k), 200000)
    diff = git.diff_filtered(staged=False)
    assert "changed" in diff["diff"]


def test_git_diff_respects_max_bytes(repo_root) -> None:
    app = repo_root / "src" / "app.py"
    app.write_text("x" * 5000 + "\n", encoding="utf-8")
    git = GitController(repo_root, lambda *a, **k: run_git(repo_root, *a, **k), 500)
    diff = git.diff_filtered(staged=False, max_bytes=500)
    assert diff["truncated"] is True
    assert len(diff["diff"].encode("utf-8")) <= 500
