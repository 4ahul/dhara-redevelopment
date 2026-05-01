"""Response structure returned by dispatcher.generate."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeasibilityReportResponse:
    excel_bytes: bytes | None
    file_path: str | None = None
    cells_written: int = 0
    missing_fields: list[str] = field(default_factory=list)
    calculation_errors: list[tuple[str, str]] = field(default_factory=list)
    skipped_formula_cells: list[str] = field(default_factory=list)
    # cell → "YYYY-MM-DD" expiry date for cells with expires_in_days
    expiring_cells: dict[str, str] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
