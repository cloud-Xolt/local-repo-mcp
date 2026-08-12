from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from gui.config_codec import coerce_dataclass, protect_secret, unprotect_secret
from gui.config_io import read_json_object
from repo.worktree import inspect_worktree
from security.tokens import http_token_problem

APP_NAME = "local-repo-mcp"


def _expanded_env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    expanded = os.path.expandvars(raw)
    if os.name == "nt" and "%" in expanded:
        return None
    try:
        return Path(expanded).expanduser()
    except RuntimeError:
        return None


def _home_dir() -> Path:
    for name in ("USERPROFILE", "HOME"):
        candidate = _expanded_env_path(name)
        if candidate is not None:
            return candidate
    try:
        return Path.home()
    except RuntimeError:
        return Path(tempfile.gettempdir())


def _config_dir() -> Path:
    if os.name == "nt":
        appdata = _expanded_env_path("APPDATA")
        if appdata is None:
            appdata = _home_dir() / "AppData" / "Roaming"
        return appdata / "LocalRepoMCP"
    xdg = _expanded_env_path("XDG_CONFIG_HOME")
    if xdg is not None:
        return xdg / APP_NAME
    return _home_dir() / ".config" / APP_NAME


CONFIG_DIR = _config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"
SECRETS_PATH = CONFIG_DIR / "secrets.json"


def _default_audit_log() -> str:
    return str(CONFIG_DIR / "audit.jsonl")


def _default_mcp_log() -> str:
    return str(CONFIG_DIR / "mcp.jsonl")


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
    http_auth_mode: Literal["none", "bearer"] = "bearer"
    http_allowed_hosts: str = "127.0.0.1:*,localhost:*"
    http_allowed_origins: str = "http://127.0.0.1:*,http://localhost:*"
    http_json_response: bool = True
    http_stateless: bool = True
    http_max_request_bytes: int = 262_144
    http_public_url: str = ""
    http_tls_certfile: str = ""
    http_tls_keyfile: str = ""
    http_tls_client_ca: str = ""
    http_client_certfile: str = ""
    http_client_keyfile: str = ""
    http_tls_terminated_proxy: bool = False
    http_proxy_trusted_ips: str = "127.0.0.1"

    max_file_bytes: int = 200_000
    max_patch_bytes: int = 200_000
    max_search_results: int = 50
    max_output_bytes: int = 20_000
    allow_dirty_worktree: bool = False
    allow_git_commit: bool = False
    audit_log: str = field(default_factory=_default_audit_log)
    mcp_log: str = field(default_factory=_default_mcp_log)
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 3
    test_timeout_max: int = 300
    test_artifact_dir: str = "test-artifacts"
    max_test_images: int = 6
    max_test_image_bytes: int = 5 * 1024 * 1024
    max_test_image_total_bytes: int = 2 * 1024 * 1024

    tunnel_client_path: str = "tunnel-client"
    tunnel_id: str = ""
    tunnel_profile: str = "local-repo"
    tunnel_profile_path: str = ""

    control_plane_api_key: str = field(default="", repr=False, compare=False)
    http_auth_token: str = field(default="", repr=False, compare=False)

    def endpoint_url(self) -> str:
        public_url = self.http_public_url.strip()
        if public_url:
            return public_url.rstrip("/")
        return self.runtime_endpoint_url()

    def runtime_endpoint_url(self) -> str:
        host = self.http_host.strip() or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        path = self.http_path.strip() or "/mcp"
        if not path.startswith("/"):
            path = "/" + path
        scheme = "https" if self.http_tls_certfile.strip() else "http"
        return f"{scheme}://{display_host}:{self.http_port}{path}"

    def runtime_health_url(self) -> str:
        endpoint = urlsplit(self.runtime_endpoint_url())
        host = endpoint.hostname or "127.0.0.1"
        display_host = f"[{host}]" if ":" in host else host
        port = f":{endpoint.port}" if endpoint.port else ""
        return f"{endpoint.scheme}://{display_host}{port}/healthz"

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
            info = inspect_worktree(repo_text)
            if info.status == "missing":
                errors.append("repo_not_found")
            elif info.status == "not_directory":
                errors.append("repo_not_directory")
            elif info.status == "git_missing":
                errors.append("git_required")
            elif not info.ready:
                errors.append("repo_not_git")
            elif not info.is_root:
                errors.append("repo_not_git_root")

        if self.mcp_mode not in {"read", "write", "test"}:
            errors.append("mode_invalid")
        if self.transport not in {"stdio", "streamable-http"}:
            errors.append("transport_invalid")

        for value, key, low, high in (
            (self.max_file_bytes, "max_file_invalid", 1, 20_000_000),
            (self.max_patch_bytes, "max_patch_invalid", 1, 5_000_000),
            (self.max_search_results, "max_search_invalid", 1, 1000),
            (self.max_output_bytes, "max_output_invalid", 1, 2_000_000),
            (self.log_max_bytes, "log_max_bytes_invalid", 64_000, 100_000_000),
            (self.log_backup_count, "log_backup_count_invalid", 1, 20),
            (self.test_timeout_max, "test_timeout_invalid", 1, 1800),
            (self.max_test_images, "test_max_images_invalid", 1, 20),
            (self.max_test_image_bytes, "test_image_max_invalid", 1, 8 * 1024 * 1024),
            (self.max_test_image_total_bytes, "test_image_total_invalid", 1, 8 * 1024 * 1024),
        ):
            if not isinstance(value, int) or not low <= value <= high:
                errors.append(key)
        artifact_dir = self.test_artifact_dir.strip()
        if not artifact_dir:
            errors.append("test_artifact_dir_invalid")
        else:
            artifact_path = Path(artifact_dir)
            if artifact_path.is_absolute() or ".." in artifact_path.parts:
                errors.append("test_artifact_dir_invalid")
        if self.mcp_mode in {"write", "test"} and not self.audit_log.strip():
            errors.append("audit_log_required")

        if self.transport == "streamable-http":
            if not 1 <= int(self.http_port) <= 65535:
                errors.append("http_port_invalid")
            if not self.http_path.startswith("/"):
                errors.append("http_path_invalid")
            if self.http_auth_mode not in {"none", "bearer"}:
                errors.append("http_auth_invalid")
            elif self.http_auth_mode != "bearer":
                errors.append("http_auth_required")
            if not self.is_local_http() and not self.http_allowed_hosts.strip():
                errors.append("http_nonlocal_hosts_required")
            if not self.http_auth_token:
                errors.append("http_token_required")
            elif http_token_problem(self.http_auth_token) is not None:
                errors.append("http_token_weak")
            if not 1024 <= self.http_max_request_bytes <= 5_000_000:
                errors.append("http_request_size_invalid")
            has_cert = bool(self.http_tls_certfile.strip())
            has_key = bool(self.http_tls_keyfile.strip())
            if has_cert != has_key:
                errors.append("http_tls_pair_required")
            for value, key in (
                (self.http_tls_certfile, "http_tls_cert_invalid"),
                (self.http_tls_keyfile, "http_tls_key_invalid"),
                (self.http_tls_client_ca, "http_tls_ca_invalid"),
                (self.http_client_certfile, "http_client_cert_invalid"),
                (self.http_client_keyfile, "http_client_key_invalid"),
            ):
                if value.strip() and not Path(value).expanduser().is_file():
                    errors.append(key)
            if self.http_tls_client_ca.strip() and not has_cert:
                errors.append("http_tls_ca_requires_cert")
            has_client_cert = bool(self.http_client_certfile.strip())
            has_client_key = bool(self.http_client_keyfile.strip())
            if has_client_cert != has_client_key:
                errors.append("http_client_tls_pair_required")
            if self.http_tls_client_ca.strip() and not (has_client_cert and has_client_key):
                errors.append("http_client_cert_required")
            if not self.is_local_http() and not has_cert and not self.http_tls_terminated_proxy:
                errors.append("http_nonlocal_tls_required")
            if self.http_tls_terminated_proxy:
                parsed = urlsplit(self.http_public_url.strip())
                if parsed.scheme != "https" or not parsed.netloc:
                    errors.append("http_public_url_required")
            public_url = self.http_public_url.strip()
            if self.http_host.strip() in {"0.0.0.0", "::"} and not public_url:
                errors.append("http_public_url_required")
            if public_url:
                parsed = urlsplit(public_url)
                expected_path = (self.http_path.strip() or "/mcp").rstrip("/") or "/"
                actual_path = parsed.path.rstrip("/") or "/"
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.query
                    or parsed.fragment
                    or actual_path != expected_path
                ):
                    errors.append("http_public_url_invalid")
            if self.http_tls_terminated_proxy and not self.http_proxy_trusted_ips.strip():
                errors.append("http_proxy_trusted_ips_required")
        return list(dict.fromkeys(errors))

    def mcp_env(self) -> dict[str, str]:
        auth_mode = "bearer" if self.transport == "streamable-http" else self.http_auth_mode
        environment = {
            "MCP_MODE": self.mcp_mode,
            "MCP_TRANSPORT": self.transport,
            "MAX_FILE_BYTES": str(self.max_file_bytes),
            "MAX_PATCH_BYTES": str(self.max_patch_bytes),
            "MAX_SEARCH_RESULTS": str(self.max_search_results),
            "MAX_OUTPUT_BYTES": str(self.max_output_bytes),
            "ALLOW_DIRTY_WORKTREE": str(self.allow_dirty_worktree).lower(),
            "ALLOW_GIT_COMMIT": str(self.allow_git_commit).lower(),
            "AUDIT_REQUIRED": str(self.mcp_mode in {"write", "test"}).lower(),
            "AUDIT_LOG": self.audit_log.strip(),
            "MCP_LOG": self.mcp_log.strip(),
            "LOG_MAX_BYTES": str(self.log_max_bytes),
            "LOG_BACKUP_COUNT": str(self.log_backup_count),
            "TEST_TIMEOUT_MAX": str(self.test_timeout_max),
            "TEST_ARTIFACT_DIR": self.test_artifact_dir.strip() or "test-artifacts",
            "MAX_TEST_IMAGES": str(self.max_test_images),
            "MAX_TEST_IMAGE_BYTES": str(self.max_test_image_bytes),
            "MAX_TEST_IMAGE_TOTAL_BYTES": str(self.max_test_image_total_bytes),
            "HTTP_HOST": self.http_host.strip() or "127.0.0.1",
            "HTTP_PORT": str(self.http_port),
            "HTTP_PATH": self.http_path.strip() or "/mcp",
            "HTTP_AUTH_MODE": auth_mode,
            "HTTP_AUTH_TOKEN": self.http_auth_token,
            "HTTP_ALLOWED_HOSTS": self.http_allowed_hosts.strip(),
            "HTTP_ALLOWED_ORIGINS": self.http_allowed_origins.strip(),
            "HTTP_JSON_RESPONSE": str(self.http_json_response).lower(),
            "HTTP_STATELESS": str(self.http_stateless).lower(),
            "HTTP_MAX_REQUEST_BYTES": str(self.http_max_request_bytes),
            "HTTP_PUBLIC_URL": self.http_public_url.strip(),
            "HTTP_TLS_CERTFILE": self.http_tls_certfile.strip(),
            "HTTP_TLS_KEYFILE": self.http_tls_keyfile.strip(),
            "HTTP_TLS_CLIENT_CA": self.http_tls_client_ca.strip(),
            "HTTP_TLS_TERMINATED_PROXY": str(self.http_tls_terminated_proxy).lower(),
            "HTTP_PROXY_TRUSTED_IPS": self.http_proxy_trusted_ips.strip() or "127.0.0.1",
        }

        if self.repo_root.strip():
            environment["REPO_ROOT"] = str(
                Path(self.repo_root).expanduser().resolve()
            )
        return environment


def _chmod_private(path: Path) -> None:
    # Windows profile ACLs are inherited. Avoid icacls here: changing ACLs while
    # saving temporary/test files can make them unreadable and break rollback.
    if os.name != "nt" and path.exists():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _chmod_private(temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_config() -> AppConfig:
    raw = read_json_object(CONFIG_PATH)
    config = coerce_dataclass(AppConfig, raw)
    secret_data = read_json_object(SECRETS_PATH)
    config.http_auth_token = unprotect_secret(secret_data)
    config.control_plane_api_key = os.environ.get("CONTROL_PLANE_API_KEY", "")
    if not config.audit_log.strip():
        config.audit_log = _default_audit_log()
    if not config.mcp_log.strip():
        config.mcp_log = _default_mcp_log()
    if config.transport == "streamable-http":
        config.http_auth_mode = "bearer"
        config.ensure_http_token()
    return config


def save_config(config: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if config.transport == "streamable-http":
        config.http_auth_mode = "bearer"
        config.ensure_http_token()

    data = asdict(config)
    data.pop("control_plane_api_key", None)
    data.pop("http_auth_token", None)
    _write_text_atomic(CONFIG_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    _chmod_private(CONFIG_PATH)

    if config.http_auth_token:
        secret_payload = protect_secret(config.http_auth_token)
        _write_text_atomic(
            SECRETS_PATH,
            json.dumps(secret_payload, indent=2),
        )
        _chmod_private(SECRETS_PATH)
    else:
        SECRETS_PATH.unlink(missing_ok=True)

