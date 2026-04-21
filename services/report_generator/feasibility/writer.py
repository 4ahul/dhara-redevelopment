"""Formula-safe Excel writer."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class Writer:
    """Collect (cell, value) writes and apply them to a workbook in one pass."""

    def __init__(self) -> None:
        self._pending: List[Tuple[str, Any]] = []

    def stage(self, cell: str, value: Any) -> None:
        self._pending.append((cell, value))

    def flush(self, wb) -> Dict[str, Any]:
        written: List[str] = []
        skipped: List[str] = []
        for ref, value in self._pending:
            sheet, coord = ref.split("!", 1)
            if sheet not in wb.sheetnames:
                skipped.append(ref)
                continue
            cell = wb[sheet][coord]
            existing = cell.value
            if isinstance(existing, str) and existing.startswith("="):
                skipped.append(ref)
                continue
            cell.value = value
            written.append(ref)
        return {"written": written, "skipped_formula_cells": skipped}
