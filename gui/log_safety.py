from __future__ import annotations

import re


_AUTHORIZATION = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)(\bbearer\s+)([A-Za-z0-9._~+/=-]{12,})")
_NAMED_SECRET = re.compile(
    r"(?i)\b(HTTP_AUTH_TOKEN|CONTROL_PLANE_API_KEY|OPENAI_API_KEY|"
    r"RUNTIME_API_KEY|API_KEY|ACCESS_TOKEN)\s*([:=])\s*([^\s,;]+)"
)
_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|api_key|apikey|access_token)=)([^&#\s]+)"
)
_JSON_SECRET = re.compile(
    r'(?i)(["\'](?:HTTP_AUTH_TOKEN|CONTROL_PLANE_API_KEY|OPENAI_API_KEY|'
    r'RUNTIME_API_KEY|API_KEY|ACCESS_TOKEN)["\']\s*:\s*["\'])([^"\']+)(["\'])'
)


def redact_log_text(value: str) -> str:
    """Redact common credentials before process output reaches the GUI."""

    text = str(value)
    text = _AUTHORIZATION.sub(r"\1<redacted>", text)
    text = _BEARER.sub(r"\1<redacted>", text)
    text = _NAMED_SECRET.sub(r"\1\2<redacted>", text)
    text = _OPENAI_KEY.sub("sk-<redacted>", text)
    text = _JSON_SECRET.sub(r"\1<redacted>\3", text)
    return _QUERY_SECRET.sub(r"\1<redacted>", text)
