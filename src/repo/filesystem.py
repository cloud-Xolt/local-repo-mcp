import os
import re
from pathlib import Path

from security.policy_engine import PolicyEngine
from security.trust_boundary import wrap_untrusted_content

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

DANGEROUS_SEARCH_PATTERNS = re.compile(r"^\(\?[a-zA-Z]")


class RepoFilesystem:
    def __init__(self, repo_root: Path, policy: PolicyEngine, max_file_bytes: int) -> None:
        self.repo_root = repo_root.resolve()
        self.policy = policy
        self.max_file_bytes = max_file_bytes

    def resolve_path(self, path: str) -> Path:
        if not path:
            raise ValueError("path is required")

        raw = Path(path)
        target = raw if raw.is_absolute() else self.repo_root / raw
        resolved = target.resolve()

        repo_root_str = str(self.repo_root)
        resolved_str = str(resolved)
        if not resolved_str.startswith(repo_root_str + os.sep) and resolved != self.repo_root:
            raise PermissionError(f"path escapes repo root: {path}")

        rel = resolved.relative_to(self.repo_root).as_posix()
        decision = self.policy.check_read(rel)
        if not decision.allowed:
            raise PermissionError(decision.reason)

        return resolved

    def check_write_path(self, rel_path: str) -> None:
        decision = self.policy.check_write(rel_path)
        if not decision.allowed:
            raise PermissionError(decision.reason)

    @staticmethod
    def wrap_untrusted_content(content: str) -> str:
        return wrap_untrusted_content(content)

    def validate_search_query(self, query: str) -> None:
        if not query or len(query) > 200:
            raise ValueError("query is required and must be <= 200 chars")
        if DANGEROUS_SEARCH_PATTERNS.match(query):
            raise ValueError("dangerous regex pattern is not allowed")

    def list_files(self, path: str, limit: int) -> dict:
        base = self.resolve_path(path)
        files = []

        if base.is_file():
            rel = base.relative_to(self.repo_root).as_posix()
            return {"files": [rel]}

        for item in base.rglob("*"):
            rel = item.relative_to(self.repo_root).as_posix()
            if any(part in IGNORE_DIRS for part in item.relative_to(self.repo_root).parts):
                continue
            if not self.policy.check_read(rel).allowed:
                continue
            files.append(rel + ("/" if item.is_dir() else ""))
            if len(files) >= limit:
                break

        return {"repo_root": str(self.repo_root), "files": files, "truncated": len(files) >= limit}

    def read_file(self, path: str) -> dict:
        target = self.resolve_path(path)
        if not target.is_file():
            raise FileNotFoundError(path)

        size = target.stat().st_size
        if size > self.max_file_bytes:
            raise PermissionError(f"file too large: {size} bytes > {self.max_file_bytes}")

        text = target.read_text(encoding="utf-8", errors="replace")
        wrapped = self.wrap_untrusted_content(text)
        return {
            "path": target.relative_to(self.repo_root).as_posix(),
            "bytes": size,
            "content": wrapped,
            "untrusted": True,
        }
