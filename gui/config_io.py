from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _quarantine(path: Path) -> None:
    try:
        invalid = path.with_name(
            f"{path.stem}.invalid.{time.time_ns()}{path.suffix}"
        )
        os.replace(path, invalid)
    except OSError:
        pass


def read_json_object(path: Path) -> dict:
    """Read a JSON object and quarantine malformed or wrong-shaped files."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        _quarantine(path)
        return {}
    except OSError:
        return {}
    if not isinstance(payload, dict):
        _quarantine(path)
        return {}
    return payload
