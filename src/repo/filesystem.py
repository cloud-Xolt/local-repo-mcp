from __future__ import annotations

import re
from pathlib import Path

from security.guard import (
    is_read_denied,
    list_files as guard_list_files,
    read_text_file,
    validate_read_path,
    validate_write_path,
)


class RepoFilesystem:
    def __init__(self, repo_root: Path, max_file_bytes: int) -> None:
        self.repo_root = repo_root.resolve()
        self.max_file_bytes = max_file_bytes

    def list_files(self, path: str, limit: int) -> dict:
        base, _ = validate_read_path(self.repo_root, path or ".")
        limit = min(max(limit, 1), 1000)

        if base.is_file():
            rel = base.relative_to(self.repo_root).as_posix()
            return {"files": [rel], "truncated": False, "limit": limit}

        if not base.is_dir():
            raise FileNotFoundError(path)

        files, truncated = guard_list_files(base, self.repo_root, limit)
        return {"files": files, "truncated": truncated, "limit": limit}

    def read_file(self, path: str) -> dict:
        target, rel = validate_read_path(self.repo_root, path)
        if not target.is_file():
            raise FileNotFoundError(path)

        content, size = read_text_file(target, self.max_file_bytes)
        return {
            "path": rel,
            "bytes": size,
            "content": content,
            "content_trust": "untrusted_repository_data",
        }

    def check_write_path(self, rel_path: str) -> None:
        validate_write_path(self.repo_root, rel_path)
