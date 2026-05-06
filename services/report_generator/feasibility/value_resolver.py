"""Pure dotted-path lookup into a request dict."""

from __future__ import annotations

import re
from typing import Any

_SEG = re.compile(r"([^.\[\]]+)(?:\[(\d+)\])?")


def lookup(data: Any, path: str) -> Any:
    """Return value at dotted path, or None if any segment is missing."""
    if data is None:
        return None
    cur = data
    for part in path.split("."):
        m = _SEG.fullmatch(part)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
        if idx is not None:
            if not isinstance(cur, (list, tuple)):
                return None
            i = int(idx)
            if i < 0 or i >= len(cur):
                return None
            cur = cur[i]
        if cur is None:
            return None
    return cur
