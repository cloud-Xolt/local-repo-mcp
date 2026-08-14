from __future__ import annotations

from pathlib import Path

from repo.file_scope import RepoFileScope, TraversalOptions
from security.guard import read_text_file, validate_read_path, validate_write_path


class RepoFilesystem:
    def __init__(self, repo_root: Path, max_file_bytes: int) -> None:
        self.repo_root = repo_root.resolve()
        self.max_file_bytes = max_file_bytes
        self.scope = RepoFileScope(self.repo_root)

    def list_files(self, options: TraversalOptions) -> dict:
        effective_limit = min(max(options.limit, 1), 1000)
        listing = TraversalOptions(
            path=options.path or ".",
            limit=effective_limit,
            include=options.include,
            exclude=options.exclude,
            respect_gitignore=options.respect_gitignore,
            max_file_bytes=min(options.max_file_bytes, self.max_file_bytes),
        )
        files, truncated = self.scope.list_files(listing)
        return {
            "files": files,
            "truncated": truncated,
            "limit": effective_limit,
        }

    def read_file(self, path: str) -> dict:
        target, relative = validate_read_path(self.repo_root, path)
        if not target.is_file():
            raise FileNotFoundError(path)
        content, size = read_text_file(target, self.max_file_bytes)
        return {
            "path": relative,
            "bytes": size,
            "content": content,
            "content_trust": "untrusted_repository_data",
        }

    def check_write_path(self, relative: str) -> None:
        validate_write_path(self.repo_root, relative)
