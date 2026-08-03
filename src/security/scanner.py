from __future__ import annotations

import re

_PATTERNS = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    (
        "credential assignment",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    ),
)


class SecretScanner:
    """Small defense-in-depth scanner for added patch lines."""

    @staticmethod
    def added_text(patch: str) -> str:
        return "\n".join(
            line[1:]
            for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def scan_patch(self, patch: str) -> list[str]:
        added = self.added_text(patch)
        return [name for name, pattern in _PATTERNS if pattern.search(added)]

    def require_clean_patch(self, patch: str) -> None:
        matches = self.scan_patch(patch)
        if matches:
            raise PermissionError("patch appears to add credential material: " + ", ".join(matches))
