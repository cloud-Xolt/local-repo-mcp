"""本地侧组件与配置统一纳管注册表。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import yaml

from gui.config import CONFIG_PATH, PROJECT_ROOT, AppConfig, save_all

if TYPE_CHECKING:
    from gui.process_manager import ProcessManager

DATA_DIR = PROJECT_ROOT / "data"
TUNNEL_DATA_DIR = DATA_DIR / "tunnel"
TUNNEL_PROFILE_DIR = TUNNEL_DATA_DIR / "profiles"
TUNNEL_BIN_DIR = PROJECT_ROOT / "bin" / "tunnel-client"
VENV_DIR = PROJECT_ROOT / ".venv"
ENV_PATH = PROJECT_ROOT / ".env"
SERVER_PATH = PROJECT_ROOT / "server.py"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"

LOCAL_DIRS = (
    PROJECT_ROOT / "config",
    DATA_DIR,
    TUNNEL_DATA_DIR,
    TUNNEL_PROFILE_DIR,
    TUNNEL_BIN_DIR,
)


@dataclass
class LocalComponent:
    component_id: str
    name: str
    category: str
    path: Path
    description: str
    managed: bool = True


@dataclass
class ComponentStatus:
    component: LocalComponent
    ok: bool
    status: str
    detail: str = ""
    actions: list[str] = field(default_factory=list)


LOCAL_COMPONENTS: list[LocalComponent] = [
    LocalComponent("mcp_server", "MCP Server", "process", SERVER_PATH, "本地 MCP 运行时 (stdio)"),
    LocalComponent("tunnel_client", "tunnel-client（可选）", "process", TUNNEL_BIN_DIR, "仅 ChatGPT 接入需要；纯本地 MCP 可不用"),
    LocalComponent("venv", "Python 虚拟环境", "dependency", VENV_DIR, "项目隔离 Python 依赖"),
    LocalComponent("config_json", "config.json", "config", CONFIG_PATH, "GUI 主配置"),
    LocalComponent("env_file", ".env", "config", ENV_PATH, "MCP Server 环境变量"),
    LocalComponent("policy_yaml", "policy.yaml", "config", PROJECT_ROOT / "config" / "policy.yaml", "策略/RBAC/Risk"),
    LocalComponent("sessions", "sessions.json", "data", PROJECT_ROOT / "sessions.json", "Agent Session 持久化"),
    LocalComponent("audit_log", "audit.log", "data", PROJECT_ROOT / "audit.log", "审计日志"),
    LocalComponent("tunnel_profiles", "Tunnel Profiles", "data", TUNNEL_PROFILE_DIR, "tunnel-client Profile 目录"),
    LocalComponent("tunnel_state", "Tunnel 状态", "data", TUNNEL_DATA_DIR / "state.json", "tunnel 纳管状态"),
    LocalComponent("target_repo", "目标 Git 仓库", "data", PROJECT_ROOT, "REPO_ROOT 指向的仓库"),
]


def ensure_local_layout(config: AppConfig) -> None:
    for d in LOCAL_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    Path(config.sessions_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config.audit_log).parent.mkdir(parents=True, exist_ok=True)
    Path(config.policy_rules).parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists() or not ENV_PATH.exists() or not Path(config.policy_rules).exists():
        save_all(config)


def _venv_python() -> Path:
    name = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return VENV_DIR / name


def _read_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    result: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def validate_config_sync(config: AppConfig) -> list[str]:
    """检查 config.json / .env / policy.yaml 是否一致。"""
    issues: list[str] = []
    env = _read_env_file()
    expected = config.mcp_env()
    for key, value in expected.items():
        if key not in env:
            issues.append(f".env 缺少 {key}")
        elif env[key] != value:
            issues.append(f".env 中 {key} 与 config.json 不一致")

    policy_path = Path(config.policy_rules)
    if not policy_path.exists():
        issues.append(f"策略文件不存在: {policy_path}")
    else:
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        git_branches = data.get("git", {}).get("protected_branches", [])
        if git_branches != config.protected_branches:
            issues.append("policy.yaml 受保护分支与 GUI 不同步")
        write_deny = data.get("permission", {}).get("write", {}).get("deny", [])
        if write_deny != config.write_deny_patterns:
            issues.append("policy.yaml 写入 deny 与 GUI 不同步")

    if not CONFIG_PATH.exists():
        issues.append("config.json 不存在")
    return issues


def sync_all_configs(config: AppConfig) -> None:
    save_all(config)


def install_venv_dependencies(on_log: Callable[[str], None] | None = None) -> None:
    python = _venv_python()
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, cwd=str(PROJECT_ROOT))
    pip = python.parent / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    cmd = [str(pip), "install", "-r", str(REQUIREMENTS_PATH)]
    if on_log:
        on_log(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "pip install 失败").strip())
    if on_log:
        on_log("依赖安装完成")


def scan_components(config: AppConfig, pm: ProcessManager) -> list[ComponentStatus]:
    ensure_local_layout(config)
    sync_issues = validate_config_sync(config)
    statuses: list[ComponentStatus] = []

    for comp in LOCAL_COMPONENTS:
        path = comp.path
        if comp.component_id == "target_repo":
            path = Path(config.repo_root)
        elif comp.component_id == "policy_yaml":
            path = Path(config.policy_rules)
        elif comp.component_id == "sessions":
            path = Path(config.sessions_file)
        elif comp.component_id == "audit_log":
            path = Path(config.audit_log)

        ok = True
        status = "正常"
        detail = str(path)
        actions = ["打开"]

        if comp.component_id == "mcp_server":
            ok = SERVER_PATH.exists()
            status = "运行中" if pm.mcp.running else ("就绪" if ok else "缺失")
            detail = f"{SERVER_PATH} | uptime={pm.mcp.uptime}"
            actions = ["启动", "停止", "打开"]
        elif comp.component_id == "tunnel_client":
            exe = TUNNEL_BIN_DIR / ("tunnel-client.exe" if os.name == "nt" else "tunnel-client")
            installed = exe.exists() or bool(config.tunnel_client_path.strip()) or bool(shutil.which("tunnel-client"))
            ts = pm.tunnel_status(config)
            if pm.tunnel.running:
                status = "运行中"
                ok = True
            elif not config.use_tunnel and not config.tunnel_id.strip():
                status = "未启用（可选）"
                ok = True
                detail = "纯本地 MCP 无需 tunnel-client · 需要 ChatGPT 时在配置页勾选启用"
                actions = ["安装", "打开"]
            elif installed:
                status = "已就绪，未运行"
                ok = True
                detail = f"{ts.executable} | v={ts.version or '-'}"
                actions = ["安装", "启动", "停止", "Doctor", "打开"]
            else:
                status = "未安装"
                ok = not config.use_tunnel
                detail = "需要 ChatGPT 接入时再安装"
                actions = ["安装", "打开"]
        elif comp.component_id == "tunnel_profiles":
            profiles = list(path.glob("*.yaml")) if path.exists() else []
            if not config.use_tunnel and not profiles:
                ok = True
                status = "未启用（可选）"
                detail = str(path)
                actions = ["打开"]
            else:
                ok = path.exists()
                profiles = list(path.glob("*.yaml")) if path.exists() else []
                status = f"{len(profiles)} 个 Profile"
                actions = ["打开"]
        elif comp.component_id == "tunnel_state":
            if not config.use_tunnel and not path.exists():
                ok = True
                status = "未启用（可选）"
                actions = ["打开"]
            else:
                ok = True
                status = "有状态" if path.exists() else "未初始化"
                actions = ["打开"]
        elif comp.component_id == "venv":
            py = _venv_python()
            ok = py.exists()
            status = "就绪" if ok else "未创建"
            detail = str(py) if ok else "运行 start_gui.bat 可自动创建"
            actions = ["安装依赖", "打开"]
        elif comp.component_id == "config_json":
            ok = CONFIG_PATH.exists()
            status = "已同步" if ok and not sync_issues else "需同步"
            detail = str(CONFIG_PATH)
            actions = ["打开", "同步全部配置"]
        elif comp.component_id == "env_file":
            ok = ENV_PATH.exists()
            env_issues = [i for i in sync_issues if ".env" in i]
            status = "已同步" if ok and not env_issues else "需同步"
            actions = ["打开", "同步全部配置"]
        elif comp.component_id == "policy_yaml":
            ok = path.exists()
            pol_issues = [i for i in sync_issues if "policy.yaml" in i]
            status = "已同步" if ok and not pol_issues else "需同步"
            actions = ["打开", "同步全部配置"]
        elif comp.component_id == "sessions":
            ok = True
            count = 0
            if path.exists():
                import json
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    count = len(data) if isinstance(data, list) else 0
                except json.JSONDecodeError:
                    ok = False
                    status = "损坏"
            else:
                status = "空"
            detail = f"{path} | sessions={count}"
            actions = ["打开", "刷新"]
        elif comp.component_id == "audit_log":
            ok = True
            size = path.stat().st_size if path.exists() else 0
            status = "有记录" if size else "空"
            detail = f"{path} | {size} bytes"
            actions = ["打开", "清空"]
        elif comp.component_id == "target_repo":
            ok = path.exists() and (path / ".git").exists()
            status = "Git 仓库" if ok else ("路径存在" if path.exists() else "不存在")
            actions = ["打开"]

        if comp.category == "config" and sync_issues and comp.component_id in ("config_json", "env_file", "policy_yaml"):
            ok = ok and not any(
                x in sync_issues
                for x in (
                    [".env 缺少", ".env 中", "policy.yaml"],
                )
            )

        statuses.append(
            ComponentStatus(
                component=comp,
                ok=ok,
                status=status,
                detail=detail,
                actions=actions,
            )
        )
    return statuses


def format_component_report(statuses: list[ComponentStatus]) -> str:
    lines = ["本地组件纳管清单", "=" * 40]
    for s in statuses:
        mark = "OK" if s.ok else "!!"
        lines.append(f"[{mark}] {s.component.name} ({s.component.category})")
        lines.append(f"     状态: {s.status}")
        lines.append(f"     路径: {s.detail}")
    return "\n".join(lines)
