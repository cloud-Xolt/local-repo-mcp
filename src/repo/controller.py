from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Callable

from repo.changes import ChangeRecord, parse_name_status_z, parse_porcelain_v1_z
from repo.git import parse_numstat_z
from repo.worktree import branch_name
from security.guard import is_read_denied


class GitController:
    def __init__(self, repo_root: Path, runner: Callable, max_output_bytes: int) -> None:
        self.repo_root = repo_root
        self.runner = runner
        self.max_output_bytes = max_output_bytes

    @staticmethod
    def _require_ok(result: subprocess.CompletedProcess[str], fallback: str) -> str:
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or fallback)
        return result.stdout

    @staticmethod
    def _blocked(record: ChangeRecord) -> bool:
        return any(is_read_denied(path) for path in record.paths)

    def current_branch(self) -> str:
        return branch_name(self.repo_root)

    def branch_warning(self) -> str | None:
        return (
            "Changes were applied on the current branch. A feature branch is recommended."
            if self.current_branch() in {"main", "master"}
            else None
        )

    _INTERRUPTED_GIT_DIRS = (
        "rebase-merge",
        "rebase-apply",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "BISECT_LOG",
        "REVERT_HEAD",
    )

    def _check_no_interrupted_operation(self) -> None:
        """Reject operations when a rebase, merge, or similar is in progress."""
        for marker in self._INTERRUPTED_GIT_DIRS:
            result = self.runner(["rev-parse", "--git-path", marker])
            if result.returncode != 0 or not result.stdout.strip():
                continue
            path = Path(result.stdout.strip())
            if not path.is_absolute():
                path = self.repo_root / path
            if path.exists():
                raise PermissionError(
                    f"repository has an in-progress operation ({marker}), "
                    "please complete or abort it first"
                )

    def is_worktree_clean(self) -> bool:
        result = self.runner(["status", "--porcelain"])
        return not self._require_ok(result, "git status failed").strip()

    def status_filtered(self) -> dict:
        result = self.runner(["status", "--porcelain=v1", "-z"])
        records = parse_porcelain_v1_z(
            self._require_ok(result, "git status failed")
        )
        visible = [
            {"status": record.status, "path": record.display_path}
            for record in records
            if not self._blocked(record)
        ]
        hidden = sum(1 for record in records if self._blocked(record))
        return {
            "branch": self.current_branch(),
            "entries": visible,
            "hidden_entries": hidden,
        }

    def _diff_records(self, staged: bool) -> list[ChangeRecord]:
        args = ["diff", "--no-ext-diff", "--no-textconv"]
        if staged:
            args.append("--cached")
        args.extend(["--name-status", "-z", "-M", "-C"])
        result = self.runner(args)
        return parse_name_status_z(
            self._require_ok(result, "git diff --name-status failed")
        )

    def diff_filtered(self, staged: bool = False, max_bytes: int | None = None) -> dict:
        effective_max = min(
            max(
                max_bytes if max_bytes is not None else self.max_output_bytes, 1
            ),
            self.max_output_bytes,
        )
        records = self._diff_records(staged)
        allowed_records = [record for record in records if not self._blocked(record)]
        hidden = len(records) - len(allowed_records)
        allowed_paths = sorted(
            {path for record in allowed_records for path in record.paths}
        )
        if not allowed_paths:
            return {
                "diff": "",
                "hidden_files": hidden,
                "truncated": False,
                "branch": self.current_branch(),
            }
        args = ["diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", *allowed_paths])
        diff = self._require_ok(self.runner(args), "git diff failed")
        encoded = diff.encode("utf-8")
        truncated = len(encoded) > effective_max
        if truncated:
            diff = encoded[:effective_max].decode("utf-8", errors="replace")
        return {
            "diff": diff,
            "hidden_files": hidden,
            "truncated": truncated,
            "branch": self.current_branch(),
        }

    def diff_for_paths(
        self,
        paths: list[str],
        max_bytes: int | None = None,
    ) -> dict:
        selected = sorted(set(paths))
        effective_max = min(
            max(max_bytes if max_bytes is not None else self.max_output_bytes, 1),
            self.max_output_bytes,
        )
        result = self.runner([
            "diff", "--no-ext-diff", "--no-textconv", "--", *selected
        ])
        full_diff = self._require_ok(result, "git diff failed")
        encoded = full_diff.encode("utf-8")
        truncated = len(encoded) > effective_max
        visible = (
            encoded[:effective_max].decode("utf-8", errors="replace")
            if truncated else full_diff
        )
        return {
            "diff": visible,
            "truncated": truncated,
            "full_hash": hashlib.sha256(encoded).hexdigest()[:16],
            "branch": self.current_branch(),
        }

    def conflicting_paths(self, actions: dict[str, str]) -> list[str]:
        if not actions:
            return []
        result = self.runner(
            [
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--",
                *sorted(actions),
            ]
        )
        records = parse_porcelain_v1_z(
            self._require_ok(result, "git status failed")
        )
        conflicts: set[str] = set()
        for record in records:
            for path in record.paths:
                action = actions.get(path)
                if action is None:
                    continue
                if record.status == "??" and action == "delete":
                    continue
                conflicts.add(path)
        return sorted(conflicts)

    def patch_targets(self, patch: str) -> list[str]:
        result = self.runner(
            ["apply", "--check", "--numstat", "-z"],
            input_text=patch,
        )
        targets = parse_numstat_z(self._require_ok(result, "invalid patch"))
        if not targets:
            raise ValueError("patch does not contain supported text-file changes")
        return targets

    def apply_patch_check(self, patch: str) -> None:
        self._check_no_interrupted_operation()
        self._require_ok(
            self.runner(
                [
                    "apply",
                    "--check",
                    "--ignore-space-change",
                    "--whitespace=nowarn",
                ],
                input_text=patch,
            ),
            "git apply --check failed",
        )

    def apply_patch(self, patch: str) -> None:
        self._require_ok(
            self.runner(
                [
                    "apply",
                    "--ignore-space-change",
                    "--whitespace=nowarn",
                ],
                input_text=patch,
            ),
            "git apply failed",
        )
