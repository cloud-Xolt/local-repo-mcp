from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from audit.logger import AuditLogger
from tools.runtime import RuntimeContext, audit_event, require_mode

T = TypeVar("T")


def _reason(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[:500]


def _audit_result_fields(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        return {}

    payload = result
    if payload.get("batch"):
        items = payload.get("results")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            payload = items[0]

    fields: dict[str, object] = {}
    code = payload.get("exit_code", payload.get("returncode"))
    if code is not None:
        fields["result_code"] = code
    for key in ("command", "command_kind", "command_status"):
        value = payload.get(key)
        if value not in (None, ""):
            fields[key] = value
    if isinstance(payload.get("files"), list):
        fields["file_count"] = len(payload["files"])
    if isinstance(payload.get("matches"), list):
        fields["match_count"] = len(payload["matches"])
    backend = payload.get("backend")
    if backend not in (None, ""):
        fields["backend"] = backend
    if payload.get("truncated") is not None:
        fields["truncated"] = bool(payload["truncated"])
    for stream in ("stderr", "stdout"):
        text = str(payload.get(stream, "")).strip()
        if text:
            fields[stream] = text[:2000]
    if not fields.get("reason"):
        reason = str(payload.get("stderr") or payload.get("stdout") or "").strip()
        if reason:
            fields["reason"] = reason[:500]
    return fields


def execute(
    context: RuntimeContext,
    *,
    tool: str,
    modes: tuple[str, ...],
    operation: Callable[[], T],
    target: str = "",
    target_is_sensitive: bool = False,
    result_status: Callable[[T], str] | None = None,
    failure_fields: Callable[[BaseException], dict[str, Any]] | None = None,
    **fields,
) -> T:
    """Run one MCP operation with one permission and audit boundary."""
    started = time.monotonic()
    record = dict(fields)
    record["tool"] = tool
    if target:
        if target_is_sensitive:
            record["target_hash"] = AuditLogger.hash_value(target)
        else:
            record["target"] = target

    # This hidden preflight is intentionally written before an operation can
    # mutate state or execute repository code. Strict audit failures therefore
    # stop write/test operations before they begin.
    audit_event(
        context,
        **record,
        event="tool_preflight",
        status="running",
        hidden=True,
    )

    try:
        require_mode(context, *modes)
    except PermissionError as exc:
        audit_event(
            context,
            **record,
            status="denied",
            denial_kind="permission_mode",
            reason=_reason(exc),
            error_type=type(exc).__name__,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise

    failure: BaseException | None = None
    try:
        result = operation()
    except PermissionError as exc:
        failure = exc
        status, kind = "denied", "policy"
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        failure = exc
        status, kind = "unavailable", "environment"
    except TimeoutError as exc:
        failure = exc
        status, kind = "failed", "timeout"
    except Exception as exc:
        failure = exc
        status, kind = "failed", "execution"
    else:
        status = result_status(result) if result_status is not None else "success"
        completion = {**_audit_result_fields(result), **record}
        completion["status"] = status
        completion["duration_ms"] = int((time.monotonic() - started) * 1000)
        audit_event(context, **completion)
        return result

    assert failure is not None
    failure_record = dict(record)
    if failure_fields is not None:
        failure_record.update(failure_fields(failure))
    audit_event(
        context,
        **failure_record,
        status=status,
        denial_kind=kind if status == "denied" else "",
        failure_kind=kind if status != "denied" else "",
        reason=_reason(failure),
        error_type=type(failure).__name__,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    raise failure
