"""Financial derivations used by black cells."""

from __future__ import annotations

from ..calc_registry import register
from ..exceptions import MissingData
from ..value_resolver import lookup


@register("bank_guarantee_15pct")
def bank_guarantee_15pct(ctx, based_on: str) -> float:
    v = ctx["resolved"].get(based_on)
    if v is None:
        raise MissingData(based_on)
    return float(v) * 0.15


@register("bank_guarantee_from_input")
def bank_guarantee_from_input(ctx, source_path: str) -> float:
    """Read a raw user input from request path and return 15% of it."""
    v = lookup(ctx["request"], source_path)
    if v is None:
        raise MissingData(source_path)
    return float(v) * 0.15


@register("percentage_of")
def percentage_of(ctx, based_on: str, pct: float) -> float:
    v = ctx["resolved"].get(based_on)
    if v is None:
        raise MissingData(based_on)
    return float(v) * float(pct)


@register("sum_resolved")
def sum_resolved(ctx, names: list[str]) -> float:
    total = 0.0
    for n in names:
        v = ctx["resolved"].get(n)
        if v is None:
            raise MissingData(n)
        total += float(v)
    return total
