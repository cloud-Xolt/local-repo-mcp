"""Windows subprocess compatibility for Local Repo MCP patch input.

Python text-mode pipes may translate patch input newlines on Windows. That can
make ``git apply`` fail against repositories that use LF line endings even
though the unified diff is valid. Keep this shim deliberately narrow: it only
changes subprocess calls whose executable is Git, whose subcommand is
``apply``, and whose input is a Python string.

Once ``src/repo/git.py`` sends patch input as bytes directly, this bootstrap
module can be removed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


if os.name == "nt":
    _original_run = subprocess.run

    def _is_git_apply(command: Any) -> bool:
        if not isinstance(command, (list, tuple)) or not command:
            return False
        executable = Path(str(command[0])).name.lower()
        return executable in {"git", "git.exe"} and "apply" in command[1:]

    def _run_without_text_translation(*popenargs: Any, **kwargs: Any):
        command = popenargs[0] if popenargs else kwargs.get("args")
        input_value = kwargs.get("input")
        if not (_is_git_apply(command) and isinstance(input_value, str)):
            return _original_run(*popenargs, **kwargs)

        encoding = kwargs.get("encoding") or "utf-8"
        errors = kwargs.get("errors") or "replace"
        binary_kwargs = dict(kwargs)
        binary_kwargs["input"] = input_value.encode(encoding, errors=errors)
        binary_kwargs.pop("text", None)
        binary_kwargs.pop("universal_newlines", None)
        binary_kwargs.pop("encoding", None)
        binary_kwargs.pop("errors", None)

        result = _original_run(*popenargs, **binary_kwargs)
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode(encoding, errors=errors)
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode(encoding, errors=errors)
        return result

    subprocess.run = _run_without_text_translation
