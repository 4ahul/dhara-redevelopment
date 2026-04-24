"""Mapping YAML loader, validator, and topological sorter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, List
from .exceptions import MappingError


@dataclass
class MappingEntry:
    cell: str
    kind: str                 # "yellow" | "black"
    semantic_name: str
    from_: Optional[str] = None       # single dotted path
    sources: Optional[List[str]] = None
    const: Any = None
    calc: Optional[str] = None
    calc_args: Optional[dict] = None
    fallback: Any = None
    transform: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None

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
    cells: List[MappingEntry] = field(default_factory=list)
    version: int = 1
    last_reviewed_by: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    generated_from_dossier: Optional[str] = None


import yaml
from pathlib import Path


_ENTRY_FIELDS = {
    "cell", "kind", "semantic_name", "from", "sources", "const",
    "calc", "calc_args", "fallback", "transform", "description", "notes",
}

_VALUE_SOURCE_KEYS = {"from", "sources", "const", "calc"}
_KINDS = {"yellow", "black"}


def validate_entry_shape(raw: dict) -> None:
    if "cell" not in raw:
        raise MappingError("entry missing 'cell'")
    if "kind" not in raw or raw["kind"] not in _KINDS:
        raise MappingError(f"entry {raw.get('cell')}: kind must be one of {_KINDS}")
    if "semantic_name" not in raw or not isinstance(raw["semantic_name"], str):
        raise MappingError(f"entry {raw.get('cell')}: semantic_name missing")
    present = _VALUE_SOURCE_KEYS & set(raw)
    if len(present) != 1:
        raise MappingError(
            f"entry {raw['cell']}: exactly one of {_VALUE_SOURCE_KEYS} required, got {present or 'none'}"
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
        semantic_name=raw["semantic_name"],
        from_=raw.get("from"),
        sources=raw.get("sources"),
        const=raw.get("const"),
        calc=raw.get("calc"),
        calc_args=raw.get("calc_args"),
        fallback=raw.get("fallback"),
        transform=raw.get("transform"),
        description=raw.get("description"),
        notes=raw.get("notes"),
    )


def load_mapping(path: str) -> MappingFile:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MappingError(f"Mapping file {path} is not a YAML mapping at top level")
    cells = [_parse_entry(c) for c in raw.get("cells", [])]
    seen_cells: set[str] = set()
    seen_names: set[str] = set()
    for c in cells:
        if c.cell in seen_cells:
            raise MappingError(f"Duplicate cell: {c.cell}")
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


def topological_sort(entries: List[MappingEntry]) -> List[MappingEntry]:
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
    indeg = {n: 0 for n in names}
    graph: dict[str, list[str]] = {n: [] for n in names}
    for e in entries:
        for d in _deps_of(e, names):
            graph[d].append(e.semantic_name)
            indeg[e.semantic_name] += 1

    from collections import deque
    ready = deque(sorted(
        (n for n, d in indeg.items() if d == 0),
        key=lambda n: (0 if by_name[n].kind == "yellow" else 1, n),
    ))

    out: List[MappingEntry] = []
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


from .inspector import _fill_rgb, YELLOW_RGB, BLACK_RGB


def validate_against_workbook(mf: MappingFile, wb) -> None:
    for e in mf.cells:
        if e.sheet not in wb.sheetnames:
            raise MappingError(f"{e.cell}: sheet not in workbook")
        ws = wb[e.sheet]
        try:
            cell = ws[e.coord]
        except Exception:
            raise MappingError(f"{e.cell}: coord does not exist")
        rgb = _fill_rgb(cell)
        if e.kind == "yellow" and rgb != YELLOW_RGB:
            raise MappingError(f"{e.cell}: kind mismatch — declared yellow, actual fill={rgb}")
        if e.kind == "black" and rgb != BLACK_RGB:
            raise MappingError(f"{e.cell}: kind mismatch — declared black, actual fill={rgb}")

