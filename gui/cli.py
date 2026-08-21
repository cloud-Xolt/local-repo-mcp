from __future__ import annotations

import getpass
import secrets
from pathlib import Path

from gui.config import load_config, save_config
from gui.connection import run_connection_test
from gui.processes import ProcessManager, format_uptime
from gui.tunnel import TunnelManager
from repo.worktree import inspect_worktree


def _print(text: str = "") -> None:
    print(text, flush=True)


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except EOFError:
        _print()
        return default
    return value or default


def _prompt_secret(label: str) -> str:
    try:
        return getpass.getpass(f"{label}: ").strip()
    except EOFError:
        _print()
        return ""


def _choose(label: str, options: list[str], current: str) -> str | None:
    _print(f"{label} (current: {current})")
    for index, option in enumerate(options, start=1):
        mark = "*" if option == current else " "
        _print(f"  {index}) [{mark}] {option}")
    raw = _prompt("Select a single number", "")
    if not raw:
        return current
    if any(ch.isspace() for ch in raw) or "," in raw:
        _print("Invalid selection. Enter one number only, e.g. 3")
        return None
    try:
        index = int(raw)
    except ValueError:
        _print("Invalid selection. Enter one number only, e.g. 3")
        return None
    if not 1 <= index <= len(options):
        _print(f"Invalid selection. Choose 1-{len(options)}.")
        return None
    return options[index - 1]


def _prompt_int(label: str, current: int, low: int, high: int) -> int:
    raw = _prompt(f"{label} ({low}-{high})", str(current))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def _prompt_bool(label: str, current: bool, *, confirm_enable: str = "") -> bool:
    default = "y" if current else "n"
    raw = _prompt(f"{label} (y/n)", default).lower()
    if raw in {"", "y", "yes", "true", "1"}:
        enabled = True
    elif raw in {"n", "no", "false", "0"}:
        enabled = False
    else:
        _print("Invalid boolean; keeping previous value.")
        return current
    if enabled and not current and confirm_enable:
        check = _prompt(confirm_enable + " Type YES to confirm", "").strip()
        if check != "YES":
            _print("Cancelled.")
            return current
    return enabled


class InteractiveCLI:
    """Menu-driven headless control surface mirroring GUI essentials.

    Progressive disclosure:
    - main menu = daily path (repo/mode/transport/test/run)
    - advanced submenu = limits, write policy, artifacts, logs, HTTP/TLS
    """

    def __init__(self) -> None:
        self.config = load_config()
        self.processes = ProcessManager()
        self.tunnel = TunnelManager(self.processes)

    def run(self) -> int:
        _print("Local Repo MCP — interactive CLI (no GUI)")
        _print("Defaults are safe; open Advanced only when you need to change them.")
        _print("Ctrl+C to quit.")
        try:
            while True:
                self._show_status()
                choice = _prompt(
                    "Menu  1)repo 2)mode 3)transport 4)test 5)http "
                    "6)tunnel-cfg 7)tunnel-run 8)logs 9)save a)advanced 0)quit",
                    "",
                ).lower()
                if choice in {"0", "q", "quit", "exit"}:
                    break
                actions = {
                    "1": self._set_repo,
                    "2": self._set_mode,
                    "3": self._set_transport,
                    "4": self._test_connection,
                    "5": self._toggle_http,
                    "6": self._configure_tunnel,
                    "7": self._toggle_tunnel,
                    "8": self._show_logs,
                    "9": self._save,
                    "a": self._advanced_menu,
                }
                action = actions.get(choice)
                if action is None:
                    _print("Unknown option.")
                    continue
                try:
                    action()
                except Exception as exc:
                    _print(f"Error: {exc}")
        except KeyboardInterrupt:
            _print("\nInterrupted.")
        finally:
            self.processes.stop_all()
        return 0

    def _show_status(self) -> None:
        cfg = self.config
        repo = cfg.repo_root.strip() or "(not set)"
        http = (
            f"running pid={self.processes.mcp.pid} "
            f"uptime={format_uptime(self.processes.mcp.uptime)}"
            if self.processes.mcp.running
            else "stopped"
        )
        tunnel = (
            f"running pid={self.processes.tunnel.pid} "
            f"uptime={format_uptime(self.processes.tunnel.uptime)}"
            if self.processes.tunnel.running
            else "stopped"
        )
        key = "set" if cfg.control_plane_api_key.strip() else "empty"
        flags = []
        if cfg.allow_git_commit:
            flags.append("git-commit=on")
        if cfg.allow_dirty_worktree:
            flags.append("dirty-patch=on")
        flag_text = ("  " + " ".join(flags)) if flags else ""
        _print()
        _print("=" * 60)
        _print(f"Repo: {repo}")
        _print(f"Mode: {cfg.mcp_mode}    Transport: {cfg.transport}{flag_text}")
        _print(f"HTTP MCP: {http}")
        _print(f"Tunnel: {tunnel}")
        _print(
            f"Tunnel ID: {cfg.tunnel_id or '(empty)'}  "
            f"API Key: {key}  Proxy: {cfg.tunnel_http_proxy or '(none)'}"
        )
        _print("=" * 60)

    def _persist(self, *, require_repo: bool = True) -> None:
        if require_repo:
            errors = self.config.validate()
            if errors:
                raise RuntimeError("Config invalid: " + ", ".join(errors))
        else:
            # Still reject obviously broken numeric/path fields.
            errors = [
                key
                for key in self.config.validate()
                if key
                not in {
                    "repo_required",
                    "repo_not_found",
                    "repo_not_directory",
                    "git_required",
                    "repo_not_git",
                    "repo_not_git_root",
                }
            ]
            if errors:
                raise RuntimeError("Config invalid: " + ", ".join(errors))
        save_config(self.config)
        _print("Config saved.")

    def _save(self) -> None:
        self._persist(require_repo=bool(self.config.repo_root.strip()))

    def _set_repo(self) -> None:
        path = _prompt("Repository path", self.config.repo_root)
        if not path:
            _print("Cancelled.")
            return
        info = inspect_worktree(path)
        if not info.ready:
            raise RuntimeError(f"Repository not ready: status={info.status}")
        if not info.is_root:
            raise RuntimeError("Select the Git worktree root, not a subdirectory.")
        self.config.repo_root = str(Path(path).expanduser().resolve())
        self._persist()

    def _set_mode(self) -> None:
        _print("Modes are exclusive: read < write < test.")
        _print("test already includes write + read; pick 3 if you need patch and tests.")
        selected = _choose(
            "Permission mode",
            ["read", "write", "test"],
            self.config.mcp_mode,
        )
        if selected is None:
            return
        if selected == self.config.mcp_mode:
            _print("Unchanged.")
            return
        self.config.mcp_mode = selected  # type: ignore[assignment]
        self._persist(require_repo=False)

    def _set_transport(self) -> None:
        if self.processes.mcp.running or self.processes.tunnel.running:
            raise RuntimeError("Stop HTTP MCP and Tunnel before changing transport.")
        selected = _choose(
            "Transport",
            ["stdio", "streamable-http"],
            self.config.transport,
        )
        if selected is None:
            return
        if selected == self.config.transport:
            _print("Unchanged.")
            return
        self.config.transport = selected  # type: ignore[assignment]
        if self.config.transport == "streamable-http":
            self.config.http_auth_mode = "bearer"
            self.config.ensure_http_token()
        self._persist(require_repo=False)

    def _test_connection(self) -> None:
        self._persist()
        if self.config.transport == "streamable-http" and not self.processes.mcp.running:
            raise RuntimeError("Start HTTP MCP first.")
        _print("Running connection test...")
        result = run_connection_test(self.config, log_callback=_print)
        tools = result.get("tools") if isinstance(result, dict) else None
        count = len(tools) if isinstance(tools, list) else "?"
        _print(f"Connection OK. tools={count}")

    def _toggle_http(self) -> None:
        if self.processes.mcp.running:
            self.processes.mcp.stop()
            _print("HTTP MCP stopped.")
            return
        self.config.transport = "streamable-http"
        self.config.http_auth_mode = "bearer"
        self.config.ensure_http_token()
        self._persist()
        _print("Starting HTTP MCP...")
        self.processes.start_http(self.config)
        _print(f"HTTP MCP ready: {self.config.endpoint_url()}")

    def _configure_tunnel(self) -> None:
        self.config.tunnel_client_path = _prompt(
            "tunnel-client path",
            self.config.tunnel_client_path or "tunnel-client",
        )
        self.config.tunnel_profile = _prompt(
            "Tunnel profile",
            self.config.tunnel_profile or "local-repo",
        )
        self.config.tunnel_profile_path = _prompt(
            "Tunnel profile path override (empty = default)",
            self.config.tunnel_profile_path,
        )
        self.config.tunnel_id = _prompt("Tunnel ID", self.config.tunnel_id)
        self.config.tunnel_http_proxy = _prompt(
            "Tunnel HTTP proxy (empty = none)",
            self.config.tunnel_http_proxy,
        )
        change_key = _prompt("Set Runtime API Key now? (y/N)", "n").lower()
        if change_key in {"y", "yes"}:
            key = _prompt_secret("Runtime API Key")
            if key:
                self.config.control_plane_api_key = key
            else:
                _print("API Key unchanged.")
        self._persist(require_repo=False)

    def _toggle_tunnel(self) -> None:
        if self.processes.tunnel.running:
            self.processes.tunnel.stop()
            _print("Tunnel stopped.")
            return
        if not self.config.control_plane_api_key.strip():
            key = _prompt_secret("Runtime API Key")
            if not key:
                raise RuntimeError("Runtime API Key is required.")
            self.config.control_plane_api_key = key
        self._persist()
        if self.config.transport == "streamable-http" and not self.processes.mcp.running:
            raise RuntimeError("Start HTTP MCP before Tunnel in streamable-http mode.")
        _print("Starting Tunnel (may take a while for control-plane checks)...")
        self.tunnel.start(self.config)
        _print("Tunnel connected to control plane.")

    def _show_logs(self) -> None:
        channel = _choose("Log channel", ["mcp", "tunnel"], "tunnel")
        if channel is None:
            return
        process = self.processes.mcp if channel == "mcp" else self.processes.tunnel
        lines = process.snapshot()[-40:]
        if not lines:
            _print("(no log lines)")
            return
        _print("--- log tail ---")
        for line in lines:
            _print(line)
        _print("--- end ---")

    def _advanced_menu(self) -> None:
        while True:
            _print()
            _print("Advanced settings (leave empty / 0 to return)")
            _print("  1) Resource limits")
            _print("  2) Write / commit policy")
            _print("  3) Test artifacts & screenshots")
            _print("  4) Audit / MCP logs")
            _print("  5) HTTP / TLS (streamable-http)")
            _print("  0) Back")
            choice = _prompt("Advanced", "0").lower()
            if choice in {"0", "b", "back", ""}:
                return
            actions = {
                "1": self._advanced_limits,
                "2": self._advanced_write_policy,
                "3": self._advanced_artifacts,
                "4": self._advanced_logs,
                "5": self._advanced_http,
            }
            action = actions.get(choice)
            if action is None:
                _print("Unknown option.")
                continue
            try:
                action()
                self._persist(require_repo=False)
            except Exception as exc:
                _print(f"Error: {exc}")

    def _advanced_limits(self) -> None:
        cfg = self.config
        _print("Leave defaults unless the client hits size/timeout limits.")
        cfg.max_file_bytes = _prompt_int(
            "Max text file size (KB)", cfg.max_file_bytes // 1000, 1, 20_000
        ) * 1000
        cfg.max_patch_bytes = _prompt_int(
            "Max patch size (KB)", cfg.max_patch_bytes // 1000, 1, 5_000
        ) * 1000
        cfg.max_search_results = _prompt_int(
            "Max search results", cfg.max_search_results, 1, 1000
        )
        cfg.max_output_bytes = _prompt_int(
            "Max command/diff output (KB)", cfg.max_output_bytes // 1000, 1, 2_000
        ) * 1000
        cfg.test_timeout_max = _prompt_int(
            "Max test timeout (seconds)", cfg.test_timeout_max, 1, 1800
        )
        cfg.max_read_image_bytes = _prompt_int(
            "repo_read_file image limit (KB)",
            cfg.max_read_image_bytes // 1024,
            1,
            8192,
        ) * 1024

    def _advanced_write_policy(self) -> None:
        cfg = self.config
        _print("These switches expand write blast radius; keep off unless required.")
        cfg.allow_dirty_worktree = _prompt_bool(
            "Allow patch overwrite of dirty target files",
            cfg.allow_dirty_worktree,
            confirm_enable="Enables overwriting local edits on patch targets.",
        )
        cfg.allow_git_commit = _prompt_bool(
            "Allow local git commit via MCP",
            cfg.allow_git_commit,
            confirm_enable="Enables repo_git_commit in write/test mode (still no push).",
        )

    def _advanced_artifacts(self) -> None:
        cfg = self.config
        cfg.test_artifact_dir = _prompt(
            "Test artifact dir (repo-relative)",
            cfg.test_artifact_dir or "test-artifacts",
        )
        cfg.max_test_images = _prompt_int(
            "Max screenshots per test", cfg.max_test_images, 1, 20
        )
        cfg.max_test_image_bytes = _prompt_int(
            "Per-screenshot limit (KB)",
            cfg.max_test_image_bytes // 1024,
            1,
            8192,
        ) * 1024
        cfg.max_test_image_total_bytes = _prompt_int(
            "Total screenshot budget per test (KB)",
            cfg.max_test_image_total_bytes // 1024,
            1,
            8192,
        ) * 1024

    def _advanced_logs(self) -> None:
        cfg = self.config
        cfg.audit_log = _prompt("Audit log path", cfg.audit_log)
        cfg.mcp_log = _prompt("MCP runtime log path", cfg.mcp_log)
        cfg.log_max_bytes = _prompt_int(
            "Log rotate size (KB)", cfg.log_max_bytes // 1000, 64, 100_000
        ) * 1000
        cfg.log_backup_count = _prompt_int(
            "Log backup count", cfg.log_backup_count, 1, 20
        )

    def _advanced_http(self) -> None:
        cfg = self.config
        _print("Used when transport=streamable-http. STDIO+Tunnel users can skip.")
        cfg.http_host = _prompt("HTTP host", cfg.http_host or "127.0.0.1")
        cfg.http_port = _prompt_int("HTTP port", cfg.http_port, 1, 65535)
        cfg.http_path = _prompt("HTTP path", cfg.http_path or "/mcp")
        cfg.http_allowed_hosts = _prompt(
            "Allowed Hosts",
            cfg.http_allowed_hosts,
        )
        cfg.http_allowed_origins = _prompt(
            "Allowed Origins",
            cfg.http_allowed_origins,
        )
        cfg.http_max_request_bytes = _prompt_int(
            "Max request body (KB)",
            max(cfg.http_max_request_bytes // 1000, 1),
            1,
            5000,
        ) * 1000
        cfg.http_public_url = _prompt(
            "Public HTTPS URL (reverse-proxy mode)",
            cfg.http_public_url,
        )
        cfg.http_tls_certfile = _prompt("TLS cert file", cfg.http_tls_certfile)
        cfg.http_tls_keyfile = _prompt("TLS key file", cfg.http_tls_keyfile)
        cfg.http_tls_client_ca = _prompt("Client CA (mTLS)", cfg.http_tls_client_ca)
        cfg.http_proxy_trusted_ips = _prompt(
            "Trusted proxy IPs/CIDRs",
            cfg.http_proxy_trusted_ips or "127.0.0.1",
        )
        cfg.http_tls_terminated_proxy = _prompt_bool(
            "TLS terminated by reverse proxy",
            cfg.http_tls_terminated_proxy,
        )
        cfg.http_json_response = _prompt_bool(
            "JSON response mode",
            cfg.http_json_response,
        )
        cfg.http_stateless = _prompt_bool("Stateless HTTP", cfg.http_stateless)
        rotate = _prompt("Rotate Bearer token now? (y/N)", "n").lower()
        if rotate in {"y", "yes"}:
            cfg.http_auth_token = secrets.token_urlsafe(32)
            _print("New Bearer token generated (saved in secrets store).")
        elif not cfg.http_auth_token:
            cfg.ensure_http_token()


def main() -> None:
    raise SystemExit(InteractiveCLI().run())


if __name__ == "__main__":
    main()
