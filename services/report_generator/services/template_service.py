"""
Template service for loading Excel feasibility templates
and managing dynamic input fields (yellow cells).
"""

import openpyxl
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from core.config import settings, resolve_scheme_key
from services.cell_mapper import cell_mapper


@dataclass
class TemplateField:
    """Represents a yellow input cell in the template."""

    sheet: str
    cell: str
    row: int
    col: int
    current_value: any
    label: str = ""


class TemplateService:
    def __init__(self):
        self._cache: Dict[str, openpyxl.Workbook] = {}
        self._field_cache: Dict[str, List[TemplateField]] = {}

    def get_template_for_scheme(
        self, scheme: str, redevelopment_type: str = "CLUBBING"
    ) -> Path:
        """Get template file path for given scheme + redevelopment type.

        Args:
            scheme: DCPR regulation key (e.g. "30(A)", "33(20)(B)")
            redevelopment_type: "CLUBBING" (default) or "INSITU"
        """
        key = resolve_scheme_key(scheme, redevelopment_type)
        template_name = settings.SCHEME_TEMPLATE_MAP[key]

        template_path = settings.TEMPLATES_DIR / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        return template_path

    def _load_workbook(self, template_path: Path) -> openpyxl.Workbook:
        """Load workbook (cached)."""
        key = str(template_path)
        if key not in self._cache:
            self._cache[key] = openpyxl.load_workbook(template_path, data_only=False)
        return self._cache[key]

    def _is_yellow_cell(self, cell) -> bool:
        """Check if a cell has yellow fill."""
        if not cell.fill or not cell.fill.fgColor:
            return False
        color = cell.fill.fgColor.rgb if hasattr(cell.fill.fgColor, "rgb") else None
        if not color:
            return False
        color_str = str(color).upper()
        return "FFFF" in color_str or color_str in ["FFFFFF00", "FFFF99", "FFFFCC"]

    def _get_cell_label(self, ws, row: int, col: int) -> str:
        """Get label for the cell prioritizing the nearest textual context visually."""
        col_letter = openpyxl.utils.get_column_letter(col)

        col_label = ""
        row_label = ""

        # 1. Vertical Scan (Find Column Header Hierarchy)
        col_labels = []
        for offset in range(1, 4):
            if row - offset >= 1:
                above_cell = ws.cell(row=row - offset, column=col)
                val = str(above_cell.value).strip() if above_cell.value else ""
                
                if val and val != "None" and not val.startswith("="):
                    # Skip digits
                    if not val.replace('.', '', 1).isdigit() and len(val) > 2:
                        # Only add if it's not a duplicate of the one below it
                        if not col_labels or val[:50] != col_labels[-1]:
                            col_labels.append(val[:50])
                            
        col_label = " - ".join(reversed(col_labels))

        # 2. Horizontal Scan (Find Row Header)
        # Traverse leftward to find the first non-numeric textual label
        for check_col in range(col - 1, 0, -1):
            cell = ws.cell(row=row, column=check_col)
            val = str(cell.value).strip() if cell.value else ""
            
            # Skip empty, Excel formulas, "None", and purely numeric data
            if not val or val == "None" or val.startswith("="):
                continue
                
            # If it's a number/float (e.g., 153.27 or 2000), it's not a label!
            if val.replace('.', '', 1).isdigit():
                continue
                
            if len(val) > 2:
                row_label = val[:50]
                break

        # 3. Composite Logic
        if row_label and col_label and row_label != col_label:
            return f"{row_label} | {col_label}"
        elif row_label:
            return row_label
        elif col_label:
            return col_label
        return f"{col_letter}{row}"

    def get_yellow_fields(
        self, scheme: str, redevelopment_type: str = "CLUBBING"
    ) -> List[TemplateField]:
        """Get all yellow (input) cells from template for given scheme."""
        key = resolve_scheme_key(scheme, redevelopment_type)
        if key in self._field_cache:
            return self._field_cache[key]

        template_path = self.get_template_for_scheme(scheme, redevelopment_type)
        wb = self._load_workbook(template_path)

        fields = []

        # Get sheets up to and including Profit & Loss Statement
        try:
            pl_idx = wb.sheetnames.index("Profit & Loss Statement")
            sheets_to_process = wb.sheetnames[: pl_idx + 1]
        except ValueError:
            sheets_to_process = wb.sheetnames[:8]  # Default first 8 sheets

        for sheet_name in sheets_to_process:
            ws = wb[sheet_name]
            for row in ws.iter_rows():
                for cell in row:
                    if self._is_yellow_cell(cell):
                        label = self._get_cell_label(ws, cell.row, cell.column)
                        fields.append(
                            TemplateField(
                                sheet=sheet_name,
                                cell=cell.coordinate,
                                row=cell.row,
                                col=cell.column,
                                current_value=cell.value,
                                label=label,
                            )
                        )

        self._field_cache[key] = fields
        return fields

    def get_template_sheets(
        self, scheme: str, redevelopment_type: str = "CLUBBING"
    ) -> List[str]:
        """Get list of sheets to copy (up to P&L)."""
        template_path = self.get_template_for_scheme(scheme, redevelopment_type)
        wb = self._load_workbook(template_path)

        try:
            pl_idx = wb.sheetnames.index("Profit & Loss Statement")
            return wb.sheetnames[: pl_idx + 1]
        except ValueError:
            return wb.sheetnames[:8]

    def apply_values(
        self, scheme: str, values: Dict[str, any], redevelopment_type: str = "CLUBBING"
    ) -> bytes:
        """Apply user values to template and return as bytes."""
        template_path = self.get_template_for_scheme(scheme, redevelopment_type)
        wb = openpyxl.load_workbook(template_path, data_only=False)

        # ── Formula Integrity Fix ───────────────────────────────────────────
        # We no longer delete extra sheets because templates often have 
        # hidden calculation sheets or Named Ranges that formulas depend on.
        # ────────────────────────────────────────────────────────────────────

        # Apply values to yellow cells using "Sheet!Cell" composite keys
        for field in self.get_yellow_fields(scheme, redevelopment_type):
            key = f"{field.sheet}!{field.cell}"
            if key in values:
                ws = wb[field.sheet]
                ws[field.cell] = values[key]

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def generate_full_report(
        self,
        scheme: str,
        all_data: Dict[str, any],
        output_path: Optional[str] = None,
        redevelopment_type: str = "CLUBBING",
    ) -> Tuple[bytes, str]:
        """Generate full feasibility report using template.

        Args:
            scheme: DCPR scheme (e.g., "33(20)(B)", "33(7)(B)")
            all_data: Dict containing all microservice data
            output_path: Optional path to save Excel file
            redevelopment_type: "CLUBBING" (default) or "INSITU"

        Returns:
            Tuple of (Excel bytes, file path or temp path)
        """
        # Resolve internal key for cell_mapper (e.g. "30(A)_INSITU")
        key = resolve_scheme_key(scheme, redevelopment_type)

        # Step 1: Map microservice data to yellow cells
        cell_values = cell_mapper.map_data_to_cells(key, all_data)

        # Step 2: Merge with manual cell overrides (if any use "Sheet!Cell" or bare "Cell" keys)
        manual_inputs = all_data.get("manual_inputs", {})
        if manual_inputs:
            for mk, mv in manual_inputs.items():
                if "!" in mk:
                    # Already has sheet prefix — use as-is
                    cell_values[mk] = mv
                # else: skip bare cell coords — they're field names not cell overrides

        # Step 3: Apply values to template
        excel_bytes = self.apply_values(scheme, cell_values, redevelopment_type)

        # Step 4: Save to file if path provided
        file_path = None
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(excel_bytes)
            file_path = output_path
        else:
            # Generate temp path
            from core.config import OUTPUT_DIR

            safe_name = all_data.get("society_name", "report").replace(" ", "_")
            output_path = str(
                OUTPUT_DIR
                / f"feasibility_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(excel_bytes)
            file_path = output_path

        return excel_bytes, file_path


template_service = TemplateService()
