from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

APP_NAME = "local-repo-mcp"


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "LocalRepoMCP"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / APP_NAME
    return Path.home() / ".config" / APP_NAME


CONFIG_DIR = _config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"
SECRETS_PATH = CONFIG_DIR / "secrets.json"


@dataclass
class AppConfig:
    language: Literal["zh", "en"] = "zh"
    appearance: Literal["system", "light", "dark"] = "system"

    repo_root: str = ""
    mcp_mode: Literal["read", "write", "test"] = "read"
    transport: Literal["stdio", "streamable-http"] = "stdio"

    http_host: str = "127.0.0.1"
    http_port: int = 8000
    http_path: str = "/mcp"
    http_auth_mode: Literal["none", "bearer"] = "none"
    http_allowed_hosts: str = "127.0.0.1:*,localhost:*"
    http_allowed_origins: str = "http://127.0.0.1:*,http://localhost:*"
    http_json_response: bool = True
    http_stateless: bool = True
    http_max_request_bytes: int = 262_144

    max_file_bytes: int = 200_000
    max_patch_bytes: int = 200_000
    max_search_results: int = 50
    max_output_bytes: int = 20_000
    allow_dirty_worktree: bool = False
    audit_log: str = ""
    test_timeout_max: int = 300

    tunnel_client_path: str = "tunnel-client"
    tunnel_id: str = ""
    tunnel_profile: str = "local-repo"

    # Memory-only. Never persisted by save_config().
    control_plane_api_key: str = field(default="", repr=False, compare=False)
    # Stored separately in secrets.json with restrictive permissions.
    http_auth_token: str = field(default="", repr=False, compare=False)

    def endpoint_url(self) -> str:
        host = self.http_host.strip() or "127.0.0.1"
        # Wildcard bind addresses are not useful client destinations. Local
        # clients and tunnel-client should connect through loopback instead.
        if host == "0.0.0.0":
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        path = self.http_path.strip() or "/mcp"
        if not path.startswith("/"):
            path = "/" + path
        return f"http://{display_host}:{self.http_port}{path}"

    def is_local_http(self) -> bool:
        return self.http_host.strip().lower() in {"127.0.0.1", "localhost", "::1"}

    def ensure_http_token(self) -> str:
        if not self.http_auth_token:
            self.http_auth_token = secrets.token_urlsafe(32)
        return self.http_auth_token

    def validate(self) -> list[str]:
        errors: list[str] = []
        repo_text = self.repo_root.strip()
        if not repo_text:
            errors.append("repo_required")
        else:
            repo = Path(repo_text).expanduser()
            if not repo.exists():
                errors.append("repo_not_found")
            elif not repo.is_dir():
                errors.append("repo_not_directory")

        if self.mcp_mode not in {"read", "write", "test"}:
            errors.append("mode_invalid")
        if self.transport not in {"stdio", "streamable-http"}:
            errors.append("transport_invalid")

        for value, key, low, high in (
            (self.max_file_bytes, "max_file_invalid", 1, 20_000_000),
            (self.max_patch_bytes, "max_patch_invalid", 1, 5_000_000),
            (self.max_search_results, "max_search_invalid", 1, 1000),
            (self.max_output_bytes, "max_output_invalid", 1, 2_000_000),
            (self.test_timeout_max, "test_timeout_invalid", 1, 1800),
        ):
            if not isinstance(value, int) or not low <= value <= high:
                errors.append(key)

        if self.transport == "streamable-http":
            if not 1 <= int(self.http_port) <= 65535:
                errors.append("http_port_invalid")
            if not self.http_path.startswith("/"):
                errors.append("http_path_invalid")
            if self.http_auth_mode not in {"none", "bearer"}:
                errors.append("http_auth_invalid")
            if not self.is_local_http():
                if self.http_auth_mode != "bearer":
                    errors.append("http_nonlocal_auth_required")
                if not self.http_allowed_hosts.strip():
                    errors.append("http_nonlocal_hosts_required")
            if self.http_auth_mode == "bearer" and not self.http_auth_token:
                errors.append("http_token_required")
            if not 1024 <= self.http_max_request_bytes <= 5_000_000:
                errors.append("http_request_size_invalid")

        return errors

    def mcp_env(self) -> dict[str, str]:
        return {
            "REPO_ROOT": str(Path(self.repo_root).expanduser().resolve()) if self.repo_root else "",
            "MCP_MODE": self.mcp_mode,
            "MCP_TRANSPORT": self.transport,
            "MAX_FILE_BYTES": str(self.max_file_bytes),
            "MAX_PATCH_BYTES": str(self.max_patch_bytes),
            "MAX_SEARCH_RESULTS": str(self.max_search_results),
            "MAX_OUTPUT_BYTES": str(self.max_output_bytes),
            "ALLOW_DIRTY_WORKTREE": str(self.allow_dirty_worktree).lower(),
            "AUDIT_LOG": self.audit_log.strip(),
            "TEST_TIMEOUT_MAX": str(self.test_timeout_max),
            "HTTP_HOST": self.http_host.strip() or "127.0.0.1",
            "HTTP_PORT": str(self.http_port),
            "HTTP_PATH": self.http_path.strip() or "/mcp",
            "HTTP_AUTH_MODE": self.http_auth_mode,
            "HTTP_AUTH_TOKEN": self.http_auth_token,
            "HTTP_ALLOWED_HOSTS": self.http_allowed_hosts.strip(),
            "HTTP_ALLOWED_ORIGINS": self.http_allowed_origins.strip(),
            "HTTP_JSON_RESPONSE": str(self.http_json_response).lower(),
            "HTTP_STATELESS": str(self.http_stateless).lower(),
            "HTTP_MAX_REQUEST_BYTES": str(self.http_max_request_bytes),
        }


def _chmod_private(path: Path) -> None:
    if os.name != "nt" and path.exists():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def load_config() -> AppConfig:
    raw = _read_json(CONFIG_PATH)
    known = {field_name for field_name in AppConfig.__dataclass_fields__}
    values = {key: value for key, value in raw.items() if key in known}
    config = AppConfig(**values)

    secret_data = _read_json(SECRETS_PATH)
    config.http_auth_token = str(secret_data.get("http_auth_token", ""))
    config.control_plane_api_key = os.environ.get("CONTROL_PLANE_API_KEY", "")
    return config


def save_config(config: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    data.pop("control_plane_api_key", None)
    data.pop("http_auth_token", None)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _chmod_private(CONFIG_PATH)

    if config.http_auth_token:
        SECRETS_PATH.write_text(
            json.dumps({"http_auth_token": config.http_auth_token}, indent=2),
            encoding="utf-8",
        )
        _chmod_private(SECRETS_PATH)
    elif SECRETS_PATH.exists():
        SECRETS_PATH.unlink()


def apply_config_to_environment(config: AppConfig) -> None:
    for key, value in config.mcp_env().items():
        if value == "" and key in {"HTTP_AUTH_TOKEN", "AUDIT_LOG"}:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
