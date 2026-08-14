from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

_PATCH_FAILED_PATH = re.compile(r"^error: patch failed: ([^:\n]+):\d+", re.MULTILINE)
_PATCH_MISSING_PATH = re.compile(
    r"^error: ([^:\n]+): No such file or directory",
    re.MULTILINE,
)

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
    "Subproject commit ",
)


def parse_patch_failure_paths(message: str) -> list[str]:
    """Extract repository-relative paths from git apply stderr."""
    paths: list[str] = []
    seen: set[str] = set()
    for pattern in (_PATCH_FAILED_PATH, _PATCH_MISSING_PATH):
        for match in pattern.finditer(message):
            path = match.group(1).strip().replace("\\", "/")
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


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


def git_list_files(
    repo_root: Path,
    *,
    respect_gitignore: bool,
    path_prefix: str = "",
) -> list[str]:
    args = ["ls-files", "-z", "--cached", "--others"]
    if respect_gitignore:
        args.append("--exclude-standard")
    else:
        args.append("--ignored")
    prefix = path_prefix.replace("\\", "/").strip("/")
    if prefix and prefix != ".":
        args.extend(["--", prefix])
    result = run_git(repo_root, args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [path.replace("\\", "/") for path in result.stdout.split("\0") if path]


def run_git(
    repo_root: Path,
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_root), "-c", f"safe.directory={repo_root}", *args]
    environment = os.environ.copy()
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_EDITOR": "true",
    })
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
            env=environment,
        )

    normalized = input_text.replace("\r\n", "\n").replace("\r", "\n")
    binary_result = subprocess.run(
        command,
        input=normalized.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
        env=environment,
    )
    return subprocess.CompletedProcess(
        args=binary_result.args,
        returncode=binary_result.returncode,
        stdout=binary_result.stdout.decode("utf-8", errors="replace"),
        stderr=binary_result.stderr.decode("utf-8", errors="replace"),
    )
