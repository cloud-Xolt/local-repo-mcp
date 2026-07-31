from __future__ import annotations

import re

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{30,}['\"]?"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]{10,}"),
]


def added_lines(patch: str) -> str:
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


class SecretScanner:
    def scan_text(self, text: str) -> list[str]:
        findings: list[str] = []
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"pattern:{pattern.pattern[:40]}")
        return findings

    def scan_patch(self, patch: str) -> list[str]:
        return self.scan_text(added_lines(patch))

    def require_clean_patch(self, patch: str) -> None:
        findings = self.scan_patch(patch)
        if findings:
            raise PermissionError(f"patch blocked by credential pattern check: {', '.join(findings)}")
