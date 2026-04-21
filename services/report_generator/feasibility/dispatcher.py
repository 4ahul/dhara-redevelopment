"""Dispatcher — orchestrates load → resolve → write. Also hosts transforms."""

from __future__ import annotations

from typing import Any, Optional


def apply_transform(value: Any, kind: Optional[str]) -> Any:
    if value is None or kind is None:
        return value
    if kind == "float":
        return float(value)
    if kind == "int":
        return int(float(value))
    if kind == "str":
        return str(value)
    if kind == "bool_toggle":
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return 1 if value else 0
        if isinstance(value, str):
            return 1 if value.strip().lower() in {"1", "true", "yes", "y", "required"} else 0
        return 0
    if kind == "percent":
        return float(value) / 100.0
    return value
