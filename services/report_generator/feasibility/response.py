"""Response structure returned by dispatcher.generate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class FeasibilityReportResponse:
    excel_bytes: bytes
    file_path: str | None = None
    cells_written: int = 0
    missing_fields: List[str] = field(default_factory=list)
    calculation_errors: List[Tuple[str, str]] = field(default_factory=list)
    skipped_formula_cells: List[str] = field(default_factory=list)
