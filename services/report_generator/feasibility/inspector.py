"""One-shot template inspector.

Scans an Excel template and emits a reviewable JSON dossier describing every
yellow-filled (input) and black-filled (computed) cell plus six context
signals per cell.
"""

from __future__ import annotations

from typing import Iterable, List, Dict, Any
import openpyxl
from openpyxl.workbook import Workbook

YELLOW_RGB = "FFFFFF00"
BLACK_RGB = "FF000000"


def _fill_rgb(cell) -> str | None:
    f = cell.fill
    if not f or f.patternType != "solid":
        return None
    fg = f.fgColor
    rgb = getattr(fg, "rgb", None) if fg else None
    return str(rgb).upper() if rgb else None


def enumerate_fillable_cells(wb: Workbook) -> List[Dict[str, Any]]:
    """Return one record per yellow- or black-filled cell across every sheet."""
    out: List[Dict[str, Any]] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                rgb = _fill_rgb(cell)
                if rgb == YELLOW_RGB:
                    kind = "yellow"
                elif rgb == BLACK_RGB:
                    kind = "black"
                else:
                    continue
                out.append(
                    {
                        "sheet": sheet_name,
                        "coord": cell.coordinate,
                        "row": cell.row,
                        "col": cell.column,
                        "kind": kind,
                        "fill_rgb": rgb,
                        "current_value": cell.value,
                    }
                )
    return out
