"""GUI 本地运维操作（无需命令行）。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from gui.config import PROJECT_ROOT

SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def open_path(path: str) -> None:
    target = Path(path)
    if target.is_file():
        target = target.parent
    if not target.exists():
        raise FileNotFoundError(f"路径不存在: {path}")
    if os.name == "nt":
        os.startfile(str(target))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=False)
    else:
        subprocess.run(["xdg-open", str(target)], check=False)


def check_environment(tunnel_client_path: str = "") -> list[dict[str, str]]:
    from gui.tunnel_manager import TUNNEL_BIN_DIR

    items: list[dict[str, str]] = []

    py = sys.executable
    items.append({"name": "Python", "ok": "是", "detail": py})

    git = shutil.which("git")
    items.append({"name": "Git", "ok": "是" if git else "否", "detail": git or "未安装"})

    docker = shutil.which("docker")
    items.append({"name": "Docker", "ok": "是" if docker else "否", "detail": docker or "测试沙箱需要"})

    rg = shutil.which("rg")
    items.append({"name": "ripgrep", "ok": "是" if rg else "否", "detail": rg or "代码搜索需要"})

    managed_exe = TUNNEL_BIN_DIR / ("tunnel-client.exe" if os.name == "nt" else "tunnel-client")
    if managed_exe.exists():
        items.append({"name": "tunnel-client (纳管)", "ok": "是", "detail": str(managed_exe)})
    else:
        tunnel = tunnel_client_path.strip() or shutil.which("tunnel-client") or ""
        items.append(
            {
                "name": "tunnel-client (可选)",
                "ok": "—",
                "detail": tunnel or "未安装 · 纯本地 MCP 不需要 · ChatGPT 接入时再装",
            }
        )

    venv = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    items.append(
        {
            "name": "虚拟环境",
            "ok": "是" if venv.exists() else "否",
            "detail": str(venv) if venv.exists() else "首次启动会自动创建",
        }
    )
    return items


def git_status(repo_root: str) -> str:
    repo = Path(repo_root).resolve()
    if not repo.exists():
        return "仓库路径不存在"
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", f"safe.directory={repo}", "status"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return result.stderr or result.stdout or "git status 失败"
    branch = subprocess.run(
        ["git", "-C", str(repo), "-c", f"safe.directory={repo}", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    head = branch.stdout.strip() if branch.returncode == 0 else "?"
    return f"分支: {head}\n\n{result.stdout}"


def git_diff(repo_root: str, max_chars: int = 8000) -> str:
    repo = Path(repo_root).resolve()
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", f"safe.directory={repo}", "diff", "--stat"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = result.stdout if result.returncode == 0 else result.stderr
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(已截断)"
    return text or "(无变更)"


def load_sessions(sessions_file: str) -> list[dict]:
    path = Path(sessions_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return []


def end_session(sessions_file: str, session_id: str) -> None:
    from session.manager import SessionManager

    manager = SessionManager(PROJECT_ROOT, Path(sessions_file))
    manager.end(session_id)


def read_audit_tail(audit_log: str, lines: int = 80) -> str:
    path = Path(audit_log)
    if not path.exists():
        return "(尚无审计记录)"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-lines:]
    return "\n".join(tail) if tail else "(空)"


def run_pytest() -> tuple[int, str]:
    python = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        python = Path(sys.executable)
    result = subprocess.run(
        [str(python), "-m", "pytest", "tests/", "-q"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip() or "(无输出)"
