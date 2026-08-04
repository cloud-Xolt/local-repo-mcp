from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from gui.config import AppConfig

_EMPTY_REMOVES = {"HTTP_AUTH_TOKEN", "AUDIT_LOG", "MCP_LOG"}


def _config_values(config: AppConfig) -> dict[str, str]:
    values = dict(config.mcp_env())
    repository = config.repo_root.strip()
    if repository:
        values["REPO_ROOT"] = str(Path(repository).expanduser().resolve())
    else:
        values.pop("REPO_ROOT", None)
    if config.transport == "streamable-http":
        values["HTTP_AUTH_MODE"] = "bearer"
        values["HTTP_AUTH_TOKEN"] = config.http_auth_token.strip()
    return values


def _validate_effective(values: Mapping[str, str]) -> None:
    transport = values.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in {"streamable-http", "http"}:
        token = values.get("HTTP_AUTH_TOKEN", "").strip()
        if len(token) < 32:
            raise ValueError(
                "Streamable HTTP requires a Bearer token of at least 32 characters"
            )


def merge_environment(
    config: AppConfig,
    base: Mapping[str, str],
    *,
    override: bool,
) -> dict[str, str]:
    """Merge persisted configuration after explicit environment precedence."""
    merged = dict(base)
    for key, value in _config_values(config).items():
        if not override and key in merged:
            continue
        if value == "" and key in _EMPTY_REMOVES:
            merged.pop(key, None)
        else:
            merged[key] = value
    _validate_effective(merged)
    return merged


def environment_for(config: AppConfig) -> dict[str, str]:
    """Return a validated child-process environment fragment."""
    values = _config_values(config)
    _validate_effective(values)
    return values


def apply_to_environment(
    config: AppConfig,
    *,
    override: bool,
) -> None:
    original = dict(os.environ)
    merged = merge_environment(config, original, override=override)
    managed = set(_config_values(config))
    managed.update(_EMPTY_REMOVES)
    for key in managed:
        if key in merged:
            os.environ[key] = merged[key]
        elif key in os.environ and (override or key not in original):
            os.environ.pop(key, None)
