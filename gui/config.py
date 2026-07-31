from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

MCP_MODES = ("read", "write", "test")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
SECRET_LEVELS = ("low", "medium", "high")

DEFAULTS = {
    "repo_root": str(PROJECT_ROOT),
    "mcp_mode": "read",
    "max_file_bytes": 200_000,
    "max_patch_bytes": 200_000,
    "max_search_results": 50,
    "max_output_bytes": 200_000,
    "allow_dirty_worktree": False,
    "audit_log": str(PROJECT_ROOT / "audit.log"),
    "git_executable": "git",
    "log_level": "INFO",
    "command_timeout": 120,
    "text_timeout": 30,
    "service_port": 8931,
    "service_mode": "stdio",
}


@dataclass
class AppConfig:
    repo_root: str = ""
    mcp_mode: str = "read"
    max_file_bytes: int = 200_000
    max_patch_bytes: int = 200_000
    max_search_results: int = 50
    max_output_bytes: int = 200_000
    allow_dirty_worktree: bool = False
    audit_log: str = ""
    tunnel_client_path: str = ""
    tunnel_id: str = ""
    tunnel_profile: str = "local-repo"
    control_plane_api_key: str = ""
    auto_start_mcp: bool = False
    use_tunnel: bool = False
    service_port: int = 8931
    service_mode: str = "stdio"
    git_executable: str = "git"
    log_level: str = "INFO"
    command_timeout: int = 120
    text_timeout: int = 30
    secret_detection_level: str = "medium"

    def __post_init__(self) -> None:
        if not self.repo_root:
            self.repo_root = str(PROJECT_ROOT)
        if not self.audit_log:
            self.audit_log = str(PROJECT_ROOT / "audit.log")
        if not self.git_executable:
            found = shutil.which("git")
            self.git_executable = found or "git"

    def mcp_env(self) -> dict[str, str]:
        return {
            "REPO_ROOT": self.repo_root,
            "MCP_MODE": self.mcp_mode,
            "MAX_FILE_BYTES": str(self.max_file_bytes),
            "MAX_PATCH_BYTES": str(self.max_patch_bytes),
            "MAX_SEARCH_RESULTS": str(self.max_search_results),
            "MAX_OUTPUT_BYTES": str(self.max_output_bytes),
            "ALLOW_DIRTY_WORKTREE": "true" if self.allow_dirty_worktree else "false",
            "AUDIT_LOG": self.audit_log,
            "SERVICE_PORT": str(self.service_port),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not Path(self.repo_root).exists():
            errors.append("仓库路径不存在")
        if self.mcp_mode not in MCP_MODES:
            errors.append("运行模式无效，仅支持 read / write / test")
        if self.max_file_bytes <= 0 or self.max_patch_bytes <= 0:
            errors.append("文件/Patch 大小限制必须大于 0")
        if self.max_search_results <= 0 or self.max_output_bytes <= 0:
            errors.append("搜索/输出大小限制必须大于 0")
        if not (1 <= self.service_port <= 65535):
            errors.append("服务端口必须在 1-65535 之间")
        return errors

    def validate_tunnel_for_start(self) -> list[str]:
        errors = self.validate()
        if not self.tunnel_id.strip():
            errors.append("请填写 Tunnel ID")
        api_key = self.control_plane_api_key.strip() or os.environ.get("CONTROL_PLANE_API_KEY", "").strip()
        if not api_key:
            errors.append("请填写 Control Plane API Key 或设置 CONTROL_PLANE_API_KEY 环境变量")
        if not self.tunnel_client_path.strip():
            errors.append("请指定 tunnel-client 可执行文件路径")
        elif not Path(self.tunnel_client_path.strip()).exists():
            errors.append("tunnel-client 路径不存在")
        return errors

    def validate_tunnel(self) -> list[str]:
        if not self.use_tunnel:
            return self.validate()
        return self.validate_tunnel_for_start()


def persisted_dict(config: AppConfig) -> dict:
    data = asdict(config)
    data.pop("control_plane_api_key", None)
    return data


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    fields = AppConfig.__dataclass_fields__
    filtered = {k: v for k, v in data.items() if k in fields}
    return AppConfig(**filtered)


def save_config(config: AppConfig) -> None:
    CONFIG_PATH.write_text(
        json.dumps(persisted_dict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if os.name != "nt":
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass


def save_all(config: AppConfig) -> None:
    save_config(config)


def reset_defaults() -> AppConfig:
    return AppConfig(**DEFAULTS)
