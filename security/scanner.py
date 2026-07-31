import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{30,}['\"]?"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)(postgres|mysql|mongodb)(://)[^\s'\"]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]{10,}"),
]


class SecretScanner:
    def scan_text(self, text: str) -> list[str]:
        findings: list[str] = []
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"pattern:{pattern.pattern[:40]}")
        findings.extend(self._scan_with_gitleaks(text))
        return findings

    def scan_patch(self, patch: str) -> list[str]:
        added_lines = []
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
        return self.scan_text("\n".join(added_lines))

    def _scan_with_gitleaks(self, text: str) -> list[str]:
        gitleaks = shutil.which("gitleaks")
        if not gitleaks:
            return []

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        result = subprocess.run(
            [gitleaks, "detect", "--no-git", "--source", tmp_path, "--redact"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode not in (0, 1):
            return []

        if result.returncode == 1 or "leaks found" in (result.stdout + result.stderr).lower():
            return ["gitleaks:potential_secret"]
        return []

    def require_clean_patch(self, patch: str) -> None:
        findings = self.scan_patch(patch)
        if findings:
            raise PermissionError(f"patch blocked by secret scanner: {', '.join(findings)}")
