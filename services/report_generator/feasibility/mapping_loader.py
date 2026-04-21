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


def _parse_entry(raw: dict) -> MappingEntry:
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
    return MappingFile(
        template=raw["template"],
        scheme=raw["scheme"],
        cells=cells,
        version=raw.get("version", 1),
        last_reviewed_by=raw.get("last_reviewed_by"),
        last_reviewed_at=raw.get("last_reviewed_at"),
        generated_from_dossier=raw.get("generated_from_dossier"),
    )
