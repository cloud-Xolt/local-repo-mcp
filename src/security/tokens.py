from __future__ import annotations


_PLACEHOLDER_FRAGMENTS = (
    "change_me",
    "changeme",
    "replace-with",
    "replace_with",
    "example-token",
    "example_token",
    "your-token",
    "your_token",
)


def http_token_problem(value: str) -> str | None:
    token = value.strip()
    if len(token) < 32:
        return "must contain at least 32 characters"
    normalized = token.casefold()
    if any(fragment in normalized for fragment in _PLACEHOLDER_FRAGMENTS):
        return "must not use a documented placeholder value"
    if len(set(token)) < 8:
        return "does not contain enough variation"
    return None


def require_strong_http_token(value: str) -> str:
    problem = http_token_problem(value)
    if problem is not None:
        raise ValueError(f"HTTP_AUTH_TOKEN {problem}")
    return value.strip()
