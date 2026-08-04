from __future__ import annotations

import base64
import ctypes
import os
from dataclasses import fields
from typing import Any, TypeVar

T = TypeVar("T")


def coerce_dataclass(cls: type[T], raw: dict[str, Any]) -> T:
    defaults = cls()
    values: dict[str, Any] = {}
    for item in fields(defaults):
        if item.name in {"control_plane_api_key", "http_auth_token"}:
            continue
        default = getattr(defaults, item.name)
        value = raw.get(item.name, default)
        try:
            if isinstance(default, bool):
                if isinstance(value, bool):
                    parsed = value
                elif isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                        raise ValueError
                    parsed = normalized in {"true", "1", "yes", "on"}
                else:
                    raise ValueError
            elif isinstance(default, int):
                if isinstance(value, bool):
                    raise ValueError
                parsed = int(value)
            elif isinstance(default, str):
                parsed = str(value) if value is not None else default
            else:
                parsed = value
        except (TypeError, ValueError, OverflowError):
            parsed = default
        values[item.name] = parsed

    allowed = {
        "language": {"zh", "en"},
        "appearance": {"system", "light", "dark"},
        "mcp_mode": {"read", "write", "test"},
        "transport": {"stdio", "streamable-http"},
        "http_auth_mode": {"none", "bearer"},
    }
    for name, choices in allowed.items():
        if values.get(name) not in choices:
            values[name] = getattr(defaults, name)
    return cls(**values)


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes = b"") -> tuple[_DATA_BLOB, ctypes.Array | None]:
    buffer = ctypes.create_string_buffer(data) if data else None
    pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)) if buffer else None
    return _DATA_BLOB(len(data), pointer), buffer


def _windows_crypto():
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.c_wchar_p,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_bool
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_bool
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def protect_secret(value: str) -> dict[str, str]:
    if not value:
        return {}
    if os.name != "nt":
        return {"http_auth_token": value}

    source, source_buffer = _blob(value.encode("utf-8"))
    output, _ = _blob()
    crypt32, kernel32 = _windows_crypto()
    if not crypt32.CryptProtectData(
        ctypes.byref(source), "Local Repo MCP HTTP token", None, None, None,
        0x1, ctypes.byref(output),
    ):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        protected = ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
    _ = source_buffer
    return {"http_auth_token_dpapi": base64.b64encode(protected).decode("ascii")}


def unprotect_secret(payload: dict[str, Any]) -> str:
    if os.name != "nt":
        return str(payload.get("http_auth_token", ""))
    encoded = str(payload.get("http_auth_token_dpapi", ""))
    if not encoded:
        # Migrate secrets written by releases that predated DPAPI support.
        return str(payload.get("http_auth_token", ""))
    try:
        protected = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return ""
    source, source_buffer = _blob(protected)
    output, _ = _blob()
    crypt32, kernel32 = _windows_crypto()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(output),
    ):
        return ""
    try:
        value = ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(output.pbData)
    _ = source_buffer
    return value
