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


@register("commercial_bua_formula")
def commercial_bua_formula(ctx, total_fsi_cell: str, pct_path: str) -> str:
    """Return an Excel formula string to calculate commercial BUA based on a percentage of total FSI."""
    pct = lookup(ctx["request"], pct_path)
    if pct is None:
        # Fallback: if num_commercial > 0, maybe default to 10%? 
        # But for now, let's just return 0 or keep it as user input if missing.
        return "0"
    
    try:
        pct_val = float(pct) / 100.0
        return f"={total_fsi_cell} * {pct_val}"
    except (ValueError, TypeError):
        return "0"
@register("incentive_bua_33_7_b")
def incentive_bua_33_7_b(ctx):
    """
    Rule: If society age > 30 years:
    Incentive = max(10 sq.m * num_flats, 15% * existing_bua_sqft)
    """
    age = lookup(ctx["request"], "society_age")
    num_flats = lookup(ctx["request"], "num_flats")
    existing_bua = lookup(ctx["request"], "existing_bua_sqft")

    if age is None or num_flats is None or existing_bua is None:
        return 0.0
    
    try:
        if float(age) <= 30:
            return 0.0
        
        # 10 sq.m converted to sqft
        tenement_incentive = float(num_flats) * 10.0 * SQM_TO_SQFT
        bua_incentive = float(existing_bua) * 0.15
        
        return max(tenement_incentive, bua_incentive)
    except (ValueError, TypeError):
        return 0.0

