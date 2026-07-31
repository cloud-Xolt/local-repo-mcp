from __future__ import annotations


def build_ripgrep_command(query: str) -> list[str]:
    """Build a fixed-string ripgrep command that cannot treat query as an option."""
    return [
        "rg", "--json", "--fixed-strings", "--line-number", "--hidden",
        "--glob", "!.git/**", "--glob", "!node_modules/**", "--glob", "!vendor/**",
        "--glob", "!.venv/**", "-e", query, "--", ".",
    ]
