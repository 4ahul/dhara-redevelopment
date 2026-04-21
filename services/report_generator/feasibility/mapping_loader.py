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
