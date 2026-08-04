from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from audit.logger import AuditLogger
from tools.runtime import RuntimeContext, audit_event, require_mode

T = TypeVar("T")


def execute(
    context: RuntimeContext,
    *,
    tool: str,
    modes: tuple[str, ...],
    operation: Callable[[], T],
    target: str = "",
    target_is_sensitive: bool = False,
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
    try:
        require_mode(context, *modes)
        result = operation()
    except Exception as exc:
        audit_event(
            context,
            **record,
            status="denied" if isinstance(exc, PermissionError) else "failed",
            error_type=type(exc).__name__,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise
    audit_event(
        context,
        **record,
        status="success",
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return result
