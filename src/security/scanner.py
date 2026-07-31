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
    """Blocks several common credential patterns in patch additions.

    This is deliberately small and is not a complete secret-scanning solution.
    """

    @staticmethod
    def added_text(patch: str) -> str:
        return "\n".join(
            line[1:]
            for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def require_clean_patch(self, patch: str) -> None:
        added = self.added_text(patch)
        for name, pattern in _PATTERNS:
            if pattern.search(added):
                raise PermissionError(f"patch appears to add a {name}")
