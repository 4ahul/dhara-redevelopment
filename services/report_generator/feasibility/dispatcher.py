"""Dispatcher — orchestrates load → resolve → write. Also hosts transforms."""

from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

import openpyxl

from .calc_registry import get as calc_get
from .exceptions import MissingData
from .mapping_loader import MappingEntry, load_mapping, topological_sort, validate_against_workbook
from .response import FeasibilityReportResponse
from .value_resolver import lookup
from .writer import Writer


def apply_transform(value: Any, kind: str | None) -> Any:
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


def resolve_entry(entry: MappingEntry, ctx: dict):
    if entry.const is not None:
        return entry.const

    # When sources AND calc both set: sources win (direct user value overrides formula)
    paths = entry.sources or ([entry.from_] if entry.from_ else [])
    for p in paths:
        v = lookup(ctx["request"], p)
        if v is not None:
            return v

    if entry.calc:
        fn = calc_get(entry.calc)
        return fn(ctx, **(entry.calc_args or {}))

    if not paths:
        raise MissingData(entry.cell)
    raise MissingData(entry.cell)


def generate(
    request: dict,
    mapping_path: str,
    template_path: str,
    output_path: str | None = None,
    warn_only: bool = True,
) -> FeasibilityReportResponse:
    mapping = load_mapping(mapping_path)
    wb = openpyxl.load_workbook(template_path, data_only=False)
    validate_against_workbook(mapping, wb)

    entries = topological_sort(mapping.cells)
    ctx = {"request": request, "resolved": {}, "errors": []}
    missing: list[str] = []
    writer = Writer()
    today = date.today()

    for entry in entries:
        try:
            value = resolve_entry(entry, ctx)
        except MissingData:
            missing.append(entry.cell)
            value = entry.fallback
        except Exception as e:
            ctx["errors"].append((entry.cell, repr(e)))
            value = entry.fallback
        value = apply_transform(value, entry.transform)
        ctx["resolved"][entry.semantic_name] = value
        writer.stage(entry.cell, value)

    # Collect cells with relative expiry
    expiring_cells: dict[str, str] = {}
    for entry in entries:
        if entry.expires_in_days is not None:
            expiry = today + timedelta(days=entry.expires_in_days)
            expiring_cells[entry.cell] = expiry.isoformat()

    # Gate: check if any required cell fell back to default
    required_missing = [
        entry.semantic_name
        for entry in entries
        if entry.required and entry.semantic_name in missing
    ]
    # Also flag if a required cell resolved to its fallback sentinel value (0)
    required_zero = [
        entry.semantic_name
        for entry in entries
        if entry.required
        and entry.semantic_name not in missing
        and entry.fallback is not None
        and ctx["resolved"].get(entry.semantic_name) == entry.fallback
        and entry.fallback == 0
    ]
    blocked = required_missing + required_zero
    if blocked and not warn_only:
        return FeasibilityReportResponse(
            excel_bytes=None,
            file_path=None,
            cells_written=0,
            missing_fields=missing,
            calculation_errors=ctx["errors"],
            skipped_formula_cells=[],
            expiring_cells=expiring_cells,
            success=False,
            error=f"Report blocked — required fields missing real data: {blocked}",
        )
    # warn_only: log the missing required fields but continue generating
    if blocked:
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "Required fields using fallback data (warn_only=True): %s", blocked
        )

    write_report = writer.flush(wb)

    if output_path:
        wb.save(output_path)

    buf = io.BytesIO()
    wb.save(buf)

    return FeasibilityReportResponse(
        excel_bytes=buf.getvalue(),
        file_path=output_path,
        cells_written=len(write_report["written"]),
        missing_fields=missing,
        calculation_errors=ctx["errors"],
        skipped_formula_cells=write_report["skipped_formula_cells"],
        expiring_cells=expiring_cells,
    )
