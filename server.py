import fnmatch
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Local Repo MCP")

REPO_ROOT = Path(os.environ.get("REPO_ROOT", ".")).resolve()
MCP_MODE = os.environ.get("MCP_MODE", "read").lower()
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", "200000"))
MAX_PATCH_BYTES = int(os.environ.get("MAX_PATCH_BYTES", "200000"))
ALLOW_DIRTY_WORKTREE = os.environ.get("ALLOW_DIRTY_WORKTREE", "false").lower() == "true"
AUDIT_LOG = os.environ.get("AUDIT_LOG", "./audit.log")

DENY_PATTERNS = [
    ".git/*",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*id_rsa*",
    "*credential*",
    "*credentials*",
    "*secret*",
    "*secrets*",
    "*token*",
]

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

TEST_COMMANDS = {
    "python_pytest": ["pytest", "-q"],
    "go_test": ["go", "test", "./..."],
    "node_test": ["npm", "test"],
    "node_lint": ["npm", "run", "lint"],
    "maven_test": ["mvn", "test"],
    "gradle_test": ["./gradlew", "test"],
}

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{30,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY-----"),
]


def audit(action: str, payload: Dict[str, Any]) -> None:
    Path(AUDIT_LOG).parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": int(time.time()),
        "action": action,
        "mode": MCP_MODE,
        "repo_root": str(REPO_ROOT),
        "payload": payload,
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def require_mode(*modes: str) -> None:
    if MCP_MODE not in modes:
        raise PermissionError(f"tool not allowed in MCP_MODE={MCP_MODE}; required={modes}")


def resolve_repo_path(path: str) -> Path:
    if not path:
        raise ValueError("path is required")

    raw = Path(path)
    target = raw if raw.is_absolute() else REPO_ROOT / raw
    resolved = target.resolve()

    repo_root_str = str(REPO_ROOT)
    resolved_str = str(resolved)
    if not resolved_str.startswith(repo_root_str + os.sep) and resolved != REPO_ROOT:
        raise PermissionError(f"path escapes repo root: {path}")

    rel = resolved.relative_to(REPO_ROOT).as_posix()
    if is_denied_path(rel):
        raise PermissionError(f"path denied by policy: {rel}")

    return resolved


def is_denied_path(rel_path: str) -> bool:
    rel_path = rel_path.strip("/")
    for pattern in DENY_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def run_git(args: List[str], input_text: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(REPO_ROOT)] + args
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def get_status_porcelain() -> str:
    result = run_git(["status", "--porcelain"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def ensure_clean_worktree() -> None:
    if ALLOW_DIRTY_WORKTREE:
        return
    status = get_status_porcelain()
    if status:
        raise PermissionError("worktree is not clean; refuse to apply patch")


def scan_added_secrets(patch: str) -> None:
    added_lines = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])

    joined = "\n".join(added_lines)
    for pattern in SECRET_PATTERNS:
        if pattern.search(joined):
            raise PermissionError("patch appears to add secrets or credentials")


def extract_patch_paths(patch: str) -> List[str]:
    paths = set()

    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                for p in parts[2:4]:
                    if p.startswith("a/") or p.startswith("b/"):
                        candidate = p[2:]
                        if candidate != "/dev/null":
                            paths.add(candidate)

        if line.startswith("--- ") or line.startswith("+++ "):
            p = line[4:].strip()
            if p == "/dev/null":
                continue
            if p.startswith("a/") or p.startswith("b/"):
                paths.add(p[2:])

    return sorted(paths)


def validate_patch_paths(patch: str) -> List[str]:
    paths = extract_patch_paths(patch)
    if not paths:
        raise ValueError("no target files found in patch")

    for p in paths:
        if p.startswith("/") or ".." in Path(p).parts:
            raise PermissionError(f"unsafe patch path: {p}")
        resolved = resolve_repo_path(p)
        rel = resolved.relative_to(REPO_ROOT).as_posix()
        if is_denied_path(rel):
            raise PermissionError(f"patch target denied: {rel}")

    return paths


@mcp.tool()
def repo_list_files(path: str = ".", limit: int = 200) -> Dict[str, Any]:
    """List files under repo root with sandbox and denylist enforcement."""
    audit("repo_list_files", {"path": path, "limit": limit})
    base = resolve_repo_path(path)
    files = []

    if base.is_file():
        return {"files": [base.relative_to(REPO_ROOT).as_posix()]}

    for item in base.rglob("*"):
        rel = item.relative_to(REPO_ROOT).as_posix()
        if any(part in IGNORE_DIRS for part in item.relative_to(REPO_ROOT).parts):
            continue
        if is_denied_path(rel):
            continue
        files.append(rel + ("/" if item.is_dir() else ""))
        if len(files) >= limit:
            break

    return {"repo_root": str(REPO_ROOT), "files": files, "truncated": len(files) >= limit}


@mcp.tool()
def repo_read_file(path: str) -> Dict[str, Any]:
    """Read a text file from the repository."""
    audit("repo_read_file", {"path": path})
    target = resolve_repo_path(path)

    if not target.is_file():
        raise FileNotFoundError(path)

    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        raise PermissionError(f"file too large: {size} bytes > {MAX_FILE_BYTES}")

    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": target.relative_to(REPO_ROOT).as_posix(),
        "bytes": size,
        "content": text,
    }


@mcp.tool()
def repo_search_code(query: str, limit: int = 50) -> Dict[str, Any]:
    """Search code using ripgrep."""
    audit("repo_search_code", {"query": query, "limit": limit})

    if not query or len(query) > 200:
        raise ValueError("query is required and must be <= 200 chars")

    cmd = [
        "rg",
        "--line-number",
        "--no-heading",
        "--hidden",
        "--glob",
        "!.git",
        "--glob",
        "!node_modules",
        "--glob",
        "!vendor",
        "--glob",
        "!.venv",
        query,
        str(REPO_ROOT),
    ]

    result = subprocess.run(cmd, text=True, capture_output=True, timeout=20, check=False)
    lines = []
    for line in result.stdout.splitlines()[:limit]:
        try:
            file_path, line_no, content = line.split(":", 2)
            rel = Path(file_path).resolve().relative_to(REPO_ROOT).as_posix()
            if not is_denied_path(rel):
                lines.append({"path": rel, "line": int(line_no), "text": content[:500]})
        except Exception:
            continue

    return {"matches": lines, "truncated": len(lines) >= limit}


@mcp.tool()
def repo_git_status() -> Dict[str, Any]:
    """Return git status in porcelain format."""
    audit("repo_git_status", {})
    result = run_git(["status", "--short"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return {"status": result.stdout}


@mcp.tool()
def repo_git_diff(staged: bool = False, max_bytes: int = 200000) -> Dict[str, Any]:
    """Return git diff."""
    audit("repo_git_diff", {"staged": staged, "max_bytes": max_bytes})
    args = ["diff", "--cached"] if staged else ["diff"]
    result = run_git(args, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    diff = result.stdout
    truncated = False
    if len(diff.encode("utf-8")) > max_bytes:
        diff = diff[:max_bytes]
        truncated = True

    return {"diff": diff, "truncated": truncated}


@mcp.tool()
def repo_apply_patch(patch: str) -> Dict[str, Any]:
    """Apply a unified diff patch after policy checks. Does not commit or push."""
    require_mode("write", "test", "ship")
    audit("repo_apply_patch", {"patch_bytes": len(patch.encode("utf-8"))})

    patch_bytes = len(patch.encode("utf-8"))
    if patch_bytes > MAX_PATCH_BYTES:
        raise PermissionError(f"patch too large: {patch_bytes} bytes > {MAX_PATCH_BYTES}")

    ensure_clean_worktree()
    targets = validate_patch_paths(patch)
    scan_added_secrets(patch)

    check = run_git(["apply", "--check", "--whitespace=nowarn"], input_text=patch, timeout=30)
    if check.returncode != 0:
        raise RuntimeError(f"git apply --check failed:\n{check.stderr}")

    apply_result = run_git(["apply", "--whitespace=nowarn"], input_text=patch, timeout=30)
    if apply_result.returncode != 0:
        raise RuntimeError(f"git apply failed:\n{apply_result.stderr}")

    diff = run_git(["diff"], timeout=30)
    return {
        "applied": True,
        "targets": targets,
        "diff": diff.stdout[:MAX_PATCH_BYTES],
    }


@mcp.tool()
def repo_run_test(command_key: str, timeout_seconds: int = 120) -> Dict[str, Any]:
    """Run a whitelisted test command only."""
    require_mode("test", "ship")
    audit("repo_run_test", {"command_key": command_key, "timeout_seconds": timeout_seconds})

    if command_key not in TEST_COMMANDS:
        raise PermissionError(f"command_key not allowed: {command_key}")

    timeout_seconds = min(max(timeout_seconds, 1), 300)
    cmd = TEST_COMMANDS[command_key]

    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )

    return {
        "command": " ".join(shlex.quote(x) for x in cmd),
        "returncode": result.returncode,
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-20000:],
    }


if __name__ == "__main__":
    if not REPO_ROOT.exists():
        raise RuntimeError(f"REPO_ROOT does not exist: {REPO_ROOT}")
    mcp.run()
