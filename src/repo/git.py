from __future__ import annotations

import shlex
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
                paths.append(path.replace("\\", "/"))
    return sorted(set(paths))


def parse_deleted_patch_paths(patch: str) -> set[str]:
    deleted: set[str] = set()
    current_path: str | None = None
    normalized = patch.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = []
            if len(parts) >= 4 and parts[3].startswith("b/"):
                current_path = parts[3][2:].replace("\\", "/")
        elif current_path is not None and line == "+++ /dev/null":
            deleted.add(current_path)
    return deleted


class GitController:
    def __init__(self, repo_root: Path, runner: Callable, max_output_bytes: int) -> None:
        self.repo_root = repo_root
        self.runner = runner
        self.max_output_bytes = max_output_bytes

    def _require_ok(self, result: subprocess.CompletedProcess[str], fallback: str) -> str:
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or fallback)
        return result.stdout

    def current_branch(self) -> str:
        result = self.runner(["rev-parse", "--abbrev-ref", "HEAD"])
        return self._require_ok(result, "failed to get current branch").strip() or "-"

    def branch_warning(self) -> str | None:
        return (
            "Changes were applied on the current branch. A feature branch is recommended."
            if self.current_branch() in {"main", "master"}
            else None
        )

    def is_worktree_clean(self) -> bool:
        result = self.runner(["status", "--porcelain"])
        return not self._require_ok(result, "git status failed").strip()

    def status_filtered(self) -> dict:
        result = self.runner(["status", "--porcelain=v1", "-z"])
        raw = self._require_ok(result, "git status failed")
        entries: list[dict[str, str]] = []
        hidden = 0
        tokens = [token for token in raw.split("\0") if token]
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if len(token) < 3:
                continue
            status = token[:2]
            path = token[3:] if token[2:3] == " " else token[2:]
            if status[0] in {"R", "C"} and index < len(tokens):
                # Porcelain v1 -z emits destination first, then source.
                index += 1
            normalized = path.replace("\\", "/")
            if is_read_denied(normalized):
                hidden += 1
            else:
                entries.append({"status": status, "path": normalized})
        return {"branch": self.current_branch(), "entries": entries, "hidden_entries": hidden}

    def _changed_paths(self, staged: bool) -> list[str]:
        args = ["diff", "--cached", "--name-only", "-z"] if staged else ["diff", "--name-only", "-z"]
        result = self.runner(args)
        raw = self._require_ok(result, "git diff --name-only failed")
        return [path.replace("\\", "/") for path in raw.split("\0") if path.strip()]

    def diff_filtered(self, staged: bool = False, max_bytes: int | None = None) -> dict:
        effective_max = min(max(max_bytes or self.max_output_bytes, 1), self.max_output_bytes)
        changed = self._changed_paths(staged)
        allowed = [path for path in changed if not is_read_denied(path)]
        hidden = len(changed) - len(allowed)
        if not allowed:
            return {"diff": "", "hidden_files": hidden, "truncated": False, "branch": self.current_branch()}
        args = ["diff"] + (["--cached"] if staged else []) + ["--", *allowed]
        result = self.runner(args)
        diff = self._require_ok(result, "git diff failed")
        encoded = diff.encode("utf-8")
        truncated = len(encoded) > effective_max
        if truncated:
            diff = encoded[:effective_max].decode("utf-8", errors="ignore")
        return {"diff": diff, "hidden_files": hidden, "truncated": truncated, "branch": self.current_branch()}

    def conflicting_paths(self, actions: dict[str, str]) -> list[str]:
        if not actions:
            return []
        result = self.runner([
            "status", "--porcelain=v1", "-z", "--untracked-files=all",
            "--", *sorted(actions),
        ])
        raw = self._require_ok(result, "git status failed")
        conflicts: set[str] = set()
        tokens = [token for token in raw.split("\0") if token]
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if len(token) < 3:
                continue
            status = token[:2]
            path = token[3:] if token[2:3] == " " else token[2:]
            if status[0] in {"R", "C"} and index < len(tokens):
                # Keep the destination path and consume the source path.
                index += 1
            normalized = path.replace("\\", "/")
            action = actions.get(normalized)
            if action is None:
                continue
            if status == "??" and action == "delete":
                continue
            conflicts.add(normalized)
        return sorted(conflicts)

    def patch_targets(self, patch: str) -> list[str]:
        result = self.runner(["apply", "--check", "--numstat", "-z"], input_text=patch)
        targets = parse_numstat_z(self._require_ok(result, "invalid patch"))
        if not targets:
            raise ValueError("patch does not contain supported text-file changes")
        return targets

    def apply_patch_check(self, patch: str) -> None:
        self._require_ok(
            self.runner(["apply", "--check", "--whitespace=nowarn"], input_text=patch),
            "git apply --check failed",
        )

    def apply_patch(self, patch: str) -> None:
        self._require_ok(
            self.runner(["apply", "--whitespace=nowarn"], input_text=patch),
            "git apply failed",
        )


def run_git(
    repo_root: Path,
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_root), "-c", f"safe.directory={repo_root}", *args]
    if input_text is None:
        return subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )

    normalized = input_text.replace("\r\n", "\n").replace("\r", "\n")
    binary_result = subprocess.run(
        command,
        input=normalized.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return subprocess.CompletedProcess(
        args=binary_result.args,
        returncode=binary_result.returncode,
        stdout=binary_result.stdout.decode("utf-8", errors="replace"),
        stderr=binary_result.stderr.decode("utf-8", errors="replace"),
    )
