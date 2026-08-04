from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class ConnectionState:
    """GUI-owned verification state for one effective MCP configuration.

    STDIO verification is intentionally not represented as a persistent child
    process: the probe session closes after initialize/tool/repository checks.
    The state therefore means "this exact configuration was verified".
    """

    fingerprint: tuple[str, ...] | None = None
    result: dict[str, Any] | None = None
    verified_at: str = ""
    last_error: str = ""
    generation: int = 0

    @property
    def verified(self) -> bool:
        return self.fingerprint is not None and self.result is not None

    def matches(self, fingerprint: tuple[str, ...]) -> bool:
        return self.verified and self.fingerprint == fingerprint

    def mark_verified(
        self,
        fingerprint: tuple[str, ...],
        result: dict[str, Any],
    ) -> None:
        self.fingerprint = fingerprint
        self.result = dict(result)
        self.verified_at = datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
        self.last_error = ""
        self.generation += 1

    def mark_failed(self, error: str) -> None:
        self.fingerprint = None
        self.result = None
        self.verified_at = ""
        self.last_error = str(error)
        self.generation += 1

    def invalidate(self) -> None:
        if not self.verified and not self.last_error:
            return
        self.fingerprint = None
        self.result = None
        self.verified_at = ""
        self.last_error = ""
        self.generation += 1


def configuration_fingerprint(
    *,
    repository: str,
    mode: str,
    transport: str,
    endpoint: str = "",
    token: str = "",
) -> tuple[str, ...]:
    # The token is part of the equality boundary but is not logged or rendered.
    return (
        repository.strip(),
        mode.strip(),
        transport.strip(),
        endpoint.strip(),
        token,
    )
