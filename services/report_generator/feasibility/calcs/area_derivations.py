"""Area derivation calcs — unit conversions, BUA-from-carpet, conditional setbacks."""

from __future__ import annotations

from ..calc_registry import register
from ..exceptions import MissingData
from ..value_resolver import lookup

SQM_TO_SQFT = 10.7639


@register("sqft_from_sqm")
def sqft_from_sqm(ctx, source_path: str) -> float:
    v = lookup(ctx["request"], source_path)
    if v is None:
        raise MissingData(source_path)
    return float(v) * SQM_TO_SQFT


@register("bua_from_carpet")
def bua_from_carpet(ctx, carpet: str, multiplier: str) -> float:
    c = ctx["resolved"].get(carpet)
    m = ctx["resolved"].get(multiplier)
    if c is None or m is None:
        raise MissingData(f"{carpet} or {multiplier}")
    return float(c) * float(m)


@register("road_width_conditional_setback")
def road_width_conditional_setback(
    ctx, min_width: float, max_width: float, proxy_name: str
) -> float:
    rw = (ctx["request"].get("dp_report") or {}).get("road_width_m")
    if rw is None:
        raise MissingData("dp_report.road_width_m")
    if float(min_width) <= float(rw) < float(max_width):
        v = ctx["resolved"].get(proxy_name)
        if v is None:
            raise MissingData(proxy_name)
        return float(v)
    return 0.0
