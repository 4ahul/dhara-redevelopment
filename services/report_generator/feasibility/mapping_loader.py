"""Mapping YAML loader, validator, and topological sorter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import MappingError
from .inspector import BLACK_RGB, YELLOW_RGB, _fill_rgb


@dataclass
class MappingEntry:
    cell: str
    kind: str  # "yellow" | "black" | "red"
    semantic_name: str
    from_: str | None = None  # single dotted path
    sources: list[str] | None = None
    const: Any = None
    calc: str | None = None
    calc_args: dict | None = None
    fallback: Any = None
    transform: str | None = None
    description: str | None = None
    notes: str | None = None
    expires_on: str | None = None  # fixed expiry date (YYYY-MM-DD)
    expires_in_days: int | None = None  # relative: expires N days after report generation
    alert_days_before: int | None = None  # alert N days before expiry
    required: bool = False  # if True, missing data blocks generation

    @property
    def sheet(self) -> str:
        return self.cell.split("!", 1)[0]

    @property
    def coord(self) -> str:
        return self.cell.split("!", 1)[1]


@dataclass
class MappingFile:
    template: str
    scheme: str
    cells: list[MappingEntry] = field(default_factory=list)
    version: int = 1
    last_reviewed_by: str | None = None
    last_reviewed_at: str | None = None
    generated_from_dossier: str | None = None


_ENTRY_FIELDS = {
    "cell",
    "kind",
    "semantic_name",
    "from",
    "sources",
    "const",
    "calc",
    "calc_args",
    "fallback",
    "transform",
    "description",
    "notes",
    "expires_on",
    "expires_in_days",
    "alert_days_before",
    "required",
}

_VALUE_SOURCE_KEYS = {"from", "sources", "const", "calc"}
_KINDS = {"yellow", "black", "red"}


def validate_entry_shape(raw: dict) -> None:
    if "cell" not in raw:
        raise MappingError("entry missing 'cell'")
    if "kind" not in raw or raw["kind"] not in _KINDS:
        raise MappingError(f"entry {raw.get('cell')}: kind must be one of {_KINDS}")

    # Red cells don't necessarily need a value source if they are just for tracking
    if raw["kind"] == "red":
        return

    if "semantic_name" not in raw or not isinstance(raw["semantic_name"], str):
        raise MappingError(f"entry {raw.get('cell')}: semantic_name missing")
    present = _VALUE_SOURCE_KEYS & set(raw)
    # Allow sources+calc together (sources override calc when present) or const alone
    valid = len(present) == 1 or present in ({"sources", "calc"}, {"from", "calc"})
    if not valid:
        raise MappingError(
            f"entry {raw['cell']}: exactly one of {_VALUE_SOURCE_KEYS} required (or sources/from+calc), got {present or 'none'}"
        )


def _parse_entry(raw: dict) -> MappingEntry:
    validate_entry_shape(raw)
    unknown = set(raw) - _ENTRY_FIELDS
    if unknown:
        raise MappingError(f"Unknown entry field(s): {unknown} in {raw.get('cell')}")
    cell = raw.get("cell")
    if not isinstance(cell, str) or "!" not in cell:
        raise MappingError(f"entry {cell!r}: 'cell' must be of form 'Sheet!Coord'")
    return MappingEntry(
        cell=cell,
        kind=raw["kind"],
        semantic_name=raw.get("semantic_name", "unnamed"),
        from_=raw.get("from"),
        sources=raw.get("sources"),
        const=raw.get("const"),
        calc=raw.get("calc"),
        calc_args=raw.get("calc_args"),
        fallback=raw.get("fallback"),
        transform=raw.get("transform"),
        description=raw.get("description"),
        notes=raw.get("notes"),
        expires_on=raw.get("expires_on"),
        expires_in_days=raw.get("expires_in_days"),
        alert_days_before=raw.get("alert_days_before"),
        required=bool(raw.get("required", False)),
    )


def load_mapping(path: str) -> MappingFile:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MappingError(f"Mapping file {path} is not a YAML mapping at top level")
    cells = [_parse_entry(c) for c in raw.get("cells", [])]
    seen_cells: set[str] = set()
    seen_names: set[str] = set()
    for c in cells:
        # if c.cell in seen_cells:
        #    raise MappingError(f"Duplicate cell: {c.cell}")
        if c.semantic_name in seen_names:
            raise MappingError(f"Duplicate semantic_name: {c.semantic_name}")
        seen_cells.add(c.cell)
        seen_names.add(c.semantic_name)
    return MappingFile(
        template=raw["template"],
        scheme=raw["scheme"],
        cells=cells,
        version=raw.get("version", 1),
        last_reviewed_by=raw.get("last_reviewed_by"),
        last_reviewed_at=raw.get("last_reviewed_at"),
        generated_from_dossier=raw.get("generated_from_dossier"),
    )


def _deps_of(entry: MappingEntry, all_names: set[str]) -> list[str]:
    if entry.kind != "black" or not entry.calc_args:
        return []
    deps = []
    for v in entry.calc_args.values():
        if isinstance(v, str) and v in all_names:
            deps.append(v)
    return deps


def topological_sort(entries: list[MappingEntry]) -> list[MappingEntry]:
    names = {e.semantic_name for e in entries}
    by_name = {e.semantic_name: e for e in entries}

    # Strong check: any calc_args key named 'based_on' must reference a known name.
    for e in entries:
        if e.kind == "black" and e.calc_args:
            for k, v in e.calc_args.items():
                if k == "based_on" and (not isinstance(v, str) or v not in names):
                    raise MappingError(
                        f"{e.cell}: calc_args.based_on={v!r} is unknown semantic_name"
                    )

    # Kahn's algorithm
    indeg = dict.fromkeys(names, 0)
    graph: dict[str, list[str]] = {n: [] for n in names}
    for e in entries:
        for d in _deps_of(e, names):
            graph[d].append(e.semantic_name)
            indeg[e.semantic_name] += 1

    from collections import deque

    ready = deque(
        sorted(
            (n for n, d in indeg.items() if d == 0),
            key=lambda n: (0 if by_name[n].kind == "yellow" else 1, n),
        )
    )

    out: list[MappingEntry] = []
    while ready:
        n = ready.popleft()
        out.append(by_name[n])
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)

    if len(out) != len(entries):
        raise MappingError("cycle detected in calc_args dependencies")

    return out


def validate_against_workbook(mf: MappingFile, wb) -> None:
    for e in mf.cells:
        if e.sheet not in wb.sheetnames:
            raise MappingError(f"{e.cell}: sheet not in workbook")
        ws = wb[e.sheet]
        try:
            cell = ws[e.coord]
        except Exception as e:
            raise MappingError(f"{e.cell}: coord does not exist") from e
        rgb = _fill_rgb(cell)
        if e.kind == "yellow" and rgb != YELLOW_RGB:
            raise MappingError(f"{e.cell}: kind mismatch — declared yellow, actual fill={rgb}")
        if e.kind == "black" and rgb != BLACK_RGB:
            raise MappingError(f"{e.cell}: kind mismatch — declared black, actual fill={rgb}")
