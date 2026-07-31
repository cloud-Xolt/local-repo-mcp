import json
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

MCP_MODES = ("read", "write", "test", "ship")


@dataclass
class AppConfig:
    repo_root: str = ""
    mcp_mode: str = "read"
    max_file_bytes: int = 200_000
    max_patch_bytes: int = 200_000
    allow_dirty_worktree: bool = False
    audit_log: str = ""
    tunnel_id: str = ""
    control_plane_api_key: str = ""
    tunnel_client_path: str = ""
    tunnel_profile: str = "local-repo"

    def __post_init__(self) -> None:
        if not self.repo_root:
            self.repo_root = str(PROJECT_ROOT)
        if not self.audit_log:
            self.audit_log = str(PROJECT_ROOT / "audit.log")

    def mcp_env(self) -> dict[str, str]:
        return {
            "REPO_ROOT": self.repo_root,
            "MCP_MODE": self.mcp_mode,
            "MAX_FILE_BYTES": str(self.max_file_bytes),
            "MAX_PATCH_BYTES": str(self.max_patch_bytes),
            "ALLOW_DIRTY_WORKTREE": "true" if self.allow_dirty_worktree else "false",
            "AUDIT_LOG": self.audit_log,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not Path(self.repo_root).exists():
            errors.append("仓库路径不存在")
        if self.mcp_mode not in MCP_MODES:
            errors.append("运行模式无效")
        if self.max_file_bytes <= 0 or self.max_patch_bytes <= 0:
            errors.append("文件/Patch 大小限制必须大于 0")
        return errors

    def validate_tunnel(self) -> list[str]:
        errors = self.validate()
        if not self.tunnel_id.strip():
            errors.append("请填写 Tunnel ID")
        if not self.control_plane_api_key.strip():
            errors.append("请填写 Control Plane API Key")
        if self.tunnel_client_path and not Path(self.tunnel_client_path).exists():
            errors.append("tunnel-client 路径不存在")
        return errors


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})


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
