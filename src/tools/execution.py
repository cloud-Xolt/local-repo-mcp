from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from audit.logger import AuditLogger
from tools.runtime import RuntimeContext, audit_event, require_mode

T = TypeVar("T")


def _reason(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[:500]


def execute(
    context: RuntimeContext,
    *,
    tool: str,
    modes: tuple[str, ...],
    operation: Callable[[], T],
    target: str = "",
    target_is_sensitive: bool = False,
    result_status: Callable[[T], str] | None = None,
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
        extra = {}
        if isinstance(result, dict) and "returncode" in result:
            extra["result_code"] = result["returncode"]
        audit_event(
            context,
            **record,
            **extra,
            status=status,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return result

    assert failure is not None
    audit_event(
        context,
        **record,
        status=status,
        denial_kind=kind if status == "denied" else "",
        failure_kind=kind if status != "denied" else "",
        reason=_reason(failure),
        error_type=type(failure).__name__,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    raise failure
