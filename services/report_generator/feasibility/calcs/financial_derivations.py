"""Financial derivations used by black cells."""

from __future__ import annotations

from typing import List
from ..calc_registry import register
from ..exceptions import MissingData


@register("bank_guarantee_15pct")
def bank_guarantee_15pct(ctx, based_on: str) -> float:
    v = ctx["resolved"].get(based_on)
    if v is None:
        raise MissingData(based_on)
    return float(v) * 0.15


@register("percentage_of")
def percentage_of(ctx, based_on: str, pct: float) -> float:
    v = ctx["resolved"].get(based_on)
    if v is None:
        raise MissingData(based_on)
    return float(v) * float(pct)


@register("sum_resolved")
def sum_resolved(ctx, names: List[str]) -> float:
    total = 0.0
    for n in names:
        v = ctx["resolved"].get(n)
        if v is None:
            raise MissingData(n)
        total += float(v)
    return total
