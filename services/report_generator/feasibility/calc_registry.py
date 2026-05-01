"""Named Python calculation function registry for black-cell mappings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register(name: str):
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            raise ValueError(f"Duplicate calc: {name}")
        _REGISTRY[name] = fn
        return fn

    return deco


def get(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown calc: {name}")
    return _REGISTRY[name]


def is_registered(name: str) -> bool:
    return name in _REGISTRY


def _clear_for_tests() -> None:
    """Wipe the registry. Do not call outside tests."""
    _REGISTRY.clear()
