import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "policy.yaml"

MCP_MODES = ("read", "write", "test", "ship")

DEFAULT_PROTECTED_BRANCHES = ["main", "master", "release/*", "production/*"]
DEFAULT_WRITE_DENY = [
    ".env*",
    "*.pem",
    "*.key",
    ".ssh/**",
    ".git/**",
    ".github/workflows/**",
    "deploy/**",
    "terraform/**",
    "*id_rsa*",
    "*credential*",
    "*secret*",
]
DEFAULT_EXECUTE_ALLOW = [
    "python_pytest",
    "go_test",
    "node_test",
    "node_lint",
    "maven_test",
    "gradle_test",
]


@dataclass
class AppConfig:
    repo_root: str = ""
    mcp_mode: str = "read"
    max_file_bytes: int = 200_000
    max_patch_bytes: int = 200_000
    allow_dirty_worktree: bool = False
    audit_log: str = ""
    policy_rules: str = ""
    sessions_file: str = ""
    protected_branches: list[str] = field(default_factory=lambda: list(DEFAULT_PROTECTED_BRANCHES))
    write_deny_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_WRITE_DENY))
    execute_allow: list[str] = field(default_factory=lambda: list(DEFAULT_EXECUTE_ALLOW))
    sandbox_memory: str = "2g"
    sandbox_cpus: str = "2"
    sandbox_tmpfs_mb: int = 512
    test_timeout_max: int = 300
    tunnel_id: str = ""
    control_plane_api_key: str = ""
    tunnel_client_path: str = ""
    tunnel_profile: str = "local-repo"
    rbac_default_role: str = "developer"
    rbac_users: list[str] = field(default_factory=lambda: ["admin:shipper"])
    auto_start_mcp: bool = False
    use_tunnel: bool = False

    def __post_init__(self) -> None:
        if not self.repo_root:
            self.repo_root = str(PROJECT_ROOT)
        if not self.audit_log:
            self.audit_log = str(PROJECT_ROOT / "audit.log")
        if not self.policy_rules:
            self.policy_rules = str(DEFAULT_POLICY_PATH)
        if not self.sessions_file:
            self.sessions_file = str(PROJECT_ROOT / "sessions.json")

    def mcp_env(self) -> dict[str, str]:
        return {
            "REPO_ROOT": self.repo_root,
            "MCP_MODE": self.mcp_mode,
            "MAX_FILE_BYTES": str(self.max_file_bytes),
            "MAX_PATCH_BYTES": str(self.max_patch_bytes),
            "ALLOW_DIRTY_WORKTREE": "true" if self.allow_dirty_worktree else "false",
            "AUDIT_LOG": self.audit_log,
            "POLICY_RULES": self.policy_rules,
            "SESSIONS_FILE": self.sessions_file,
            "SANDBOX_MEMORY": self.sandbox_memory,
            "SANDBOX_CPUS": self.sandbox_cpus,
            "SANDBOX_TMPFS_MB": str(self.sandbox_tmpfs_mb),
            "TEST_TIMEOUT_MAX": str(self.test_timeout_max),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not Path(self.repo_root).exists():
            errors.append("仓库路径不存在")
        if self.mcp_mode not in MCP_MODES:
            errors.append("运行模式无效")
        if self.max_file_bytes <= 0 or self.max_patch_bytes <= 0:
            errors.append("文件/Patch 大小限制必须大于 0")
        if self.sandbox_tmpfs_mb <= 0:
            errors.append("沙箱 tmpfs 大小必须大于 0")
        if self.test_timeout_max <= 0:
            errors.append("测试超时上限必须大于 0")
        if self.policy_rules and not Path(self.policy_rules).parent.exists():
            errors.append("策略文件目录不存在")
        if self.sessions_file:
            Path(self.sessions_file).parent.mkdir(parents=True, exist_ok=True)
        return errors

    def validate_tunnel_for_start(self) -> list[str]:
        """启动 Tunnel / ChatGPT 接入时校验（用户主动选择）。"""
        errors = self.validate()
        if not self.tunnel_id.strip():
            errors.append("请填写 Tunnel ID")
        if not self.control_plane_api_key.strip():
            errors.append("请填写 Control Plane API Key")
        from gui.tunnel_manager import TUNNEL_BIN_DIR

        managed = TUNNEL_BIN_DIR / ("tunnel-client.exe" if os.name == "nt" else "tunnel-client")
        has_client = managed.exists() or bool(self.tunnel_client_path.strip()) or bool(shutil.which("tunnel-client"))
        if not has_client:
            errors.append("tunnel-client 未安装，请到 Tunnel 页点击「安装/更新到项目」")
        if self.tunnel_client_path and not Path(self.tunnel_client_path).exists():
            errors.append("tunnel-client 覆盖路径不存在")
        return errors

    def validate_tunnel(self) -> list[str]:
        """启用 Tunnel 选项开启时的持续校验；未启用则不强制。"""
        if not self.use_tunnel:
            return self.validate()
        return self.validate_tunnel_for_start()


def lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def list_to_lines(items: list[str]) -> str:
    return "\n".join(items)


def rbac_users_to_lines(users: dict[str, str]) -> str:
    return "\n".join(f"{user}:{role}" for user, role in sorted(users.items()))


def lines_to_rbac_users(text: str) -> dict[str, str]:
    users: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        user, role = line.split(":", 1)
        users[user.strip()] = role.strip()
    return users


def load_policy_into_config(config: AppConfig) -> AppConfig:
    path = Path(config.policy_rules)
    if not path.exists():
        return config
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    git = data.get("git", {})
    permission = data.get("permission", {})
    rbac = data.get("rbac", {})
    config.protected_branches = git.get("protected_branches", config.protected_branches)
    config.write_deny_patterns = permission.get("write", {}).get("deny", config.write_deny_patterns)
    config.execute_allow = permission.get("execute", {}).get("allow", config.execute_allow)
    config.rbac_default_role = rbac.get("default_role", config.rbac_default_role)
    users = rbac.get("users", {})
    if users:
        config.rbac_users = [f"{u}:{r}" for u, r in users.items()]
    return config


def write_policy_yaml(config: AppConfig) -> Path:
    path = Path(config.policy_rules)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    data.setdefault("repo", {})["root"] = "."
    data.setdefault("permission", {})
    data["permission"].setdefault("read", {"allow": ["**"], "deny": []})
    data["permission"]["read"]["deny"] = data["permission"]["read"].get(
        "deny",
        [
            ".env*",
            "*.pem",
            "*.key",
            ".ssh/**",
            ".git/**",
        ],
    )
    data["permission"]["write"] = {
        "allow": ["**"],
        "deny": config.write_deny_patterns,
    }
    data["permission"]["execute"] = {"allow": config.execute_allow}
    data["git"] = {"protected_branches": config.protected_branches}
    data["rbac"] = {
        "default_role": config.rbac_default_role,
        "roles": data.get("rbac", {}).get(
            "roles",
            {
                "viewer": {"permissions": ["read"]},
                "developer": {"permissions": ["read", "write"]},
                "tester": {"permissions": ["read", "write", "test", "execute"]},
                "shipper": {"permissions": ["read", "write", "test", "execute", "ship"]},
            },
        ),
        "users": lines_to_rbac_users("\n".join(config.rbac_users)),
    }
    data.setdefault("risk", {})
    data["risk"].setdefault("block_threshold", 90)
    data["risk"].setdefault("high_threshold", 70)

    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        config = AppConfig()
        return load_policy_into_config(config)
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    fields = AppConfig.__dataclass_fields__
    config = AppConfig(**{k: v for k, v in data.items() if k in fields})
    if "security/rules.yaml" in config.policy_rules.replace("\\", "/"):
        config.policy_rules = str(DEFAULT_POLICY_PATH)
    return load_policy_into_config(config)


def save_config(config: AppConfig) -> None:
    CONFIG_PATH.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_env_file(config: AppConfig) -> Path:
    env_path = PROJECT_ROOT / ".env"
    lines = [f"{k}={v}" for k, v in config.mcp_env().items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def save_all(config: AppConfig) -> None:
    save_config(config)
    write_env_file(config)
    write_policy_yaml(config)
