from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from security.guard import is_read_denied

UNSUPPORTED_PATCH_MARKERS = (
    "GIT binary patch",
    "Binary files ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "old mode ",
    "new mode ",
    "new file mode 160000",
    "deleted file mode 160000",
    "new file mode 120000",
)


def reject_unsupported_patch_types(patch: str) -> None:
    for marker in UNSUPPORTED_PATCH_MARKERS:
        if marker in patch:
            raise PermissionError(f"unsupported patch type: {marker.strip()}")


def parse_numstat_z(stdout: str) -> list[str]:
    paths: list[str] = []
    for entry in stdout.split("\0"):
        if not entry.strip():
            continue
        parts = entry.split("\t")
        if len(parts) >= 3:
            path = parts[2].strip()
            if path and path != "/dev/null":
                paths.append(path)
    return sorted(set(paths))


def parse_patch_targets(repo_root: Path, run_git: Callable, patch: str) -> list[str]:
    result = run_git(["apply", "--check", "--numstat", "-z"], input_text=patch, timeout=30)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "invalid patch")
    return parse_numstat_z(result.stdout)


class GitController:
    def __init__(self, repo_root: Path, run_git: Callable, max_output_bytes: int) -> None:
        self.repo_root = repo_root
        self.run_git = run_git
        self.max_output_bytes = max_output_bytes

    def current_branch(self) -> str:
        result = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to get branch")
        return result.stdout.strip()

    def branch_warning(self) -> str | None:
        branch = self.current_branch()
        if branch in {"main", "master"}:
            return "Changes were applied on the current branch. A feature branch is recommended."
        return None

    def is_worktree_clean(self) -> bool:
        result = self.run_git(["status", "--porcelain"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git status failed")
        return not result.stdout.strip()

    def status_filtered(self) -> dict:
        result = self.run_git(["status", "--porcelain=v1", "-z"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git status failed")

        entries: list[dict[str, str]] = []
        hidden = 0
        raw = result.stdout
        i = 0
        while i < len(raw):
            if i + 2 > len(raw):
                break
            status = raw[i : i + 2]
            i += 2
            if i < len(raw) and raw[i] == " ":
                i += 1
            path_end = raw.find("\0", i)
            if path_end == -1:
                break
            path = raw[i:path_end]
            i = path_end + 1
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            normalized = path.replace("\\", "/")
            if is_read_denied(normalized):
                hidden += 1
                continue
            entries.append({"status": status, "path": normalized})

        return {
            "branch": self.current_branch(),
            "entries": entries,
            "hidden_entries": hidden,
        }

    def _changed_paths(self, staged: bool) -> list[str]:
        args = ["diff", "--cached", "--name-only", "-z"] if staged else ["diff", "--name-only", "-z"]
        result = self.run_git(args, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git diff --name-only failed")
        return [p.replace("\\", "/") for p in result.stdout.split("\0") if p.strip()]

    def diff_filtered(self, staged: bool = False, max_bytes: int | None = None) -> dict:
        effective_max = min(max(max_bytes or self.max_output_bytes, 1), self.max_output_bytes)
        changed = self._changed_paths(staged)
        allowed: list[str] = []
        hidden = 0
        for path in changed:
            if is_read_denied(path):
                hidden += 1
            else:
                allowed.append(path)

        if not allowed:
            return {"diff": "", "hidden_files": hidden, "truncated": False, "branch": self.current_branch()}

        args = ["diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", *allowed])
        result = self.run_git(args, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git diff failed")

        diff = result.stdout
        truncated = False
        encoded = diff.encode("utf-8")
        if len(encoded) > effective_max:
            diff = encoded[:effective_max].decode("utf-8", errors="ignore")
            truncated = True

        return {
            "diff": diff,
            "hidden_files": hidden,
            "truncated": truncated,
            "branch": self.current_branch(),
        }

    def apply_patch_check(self, patch: str) -> None:
        result = self.run_git(["apply", "--check", "--whitespace=nowarn"], input_text=patch, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git apply --check failed")

    def apply_patch(self, patch: str) -> None:
        result = self.run_git(["apply", "--whitespace=nowarn"], input_text=patch, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git apply failed")

    def patch_targets(self, patch: str) -> list[str]:
        return parse_patch_targets(self.repo_root, self.run_git, patch)


def run_git(
    repo_root: Path,
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "-c",
        f"safe.directory={repo_root}",
        *args,
    ]
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
