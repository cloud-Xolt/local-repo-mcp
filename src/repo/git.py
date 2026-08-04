from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

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
