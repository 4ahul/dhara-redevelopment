"""Area derivation calcs — unit conversions, BUA-from-carpet, conditional setbacks."""

from __future__ import annotations

from ..calc_registry import register
from ..exceptions import MissingData
from ..value_resolver import lookup

SQM_TO_SQFT = 10.7639


@register("staircase_ratio_from_bua")
def staircase_ratio_from_bua(ctx) -> float:
    """N62: Staircase ratio from existing BUA — ≤500sqm=50%, ≤1000=45%, ≤2000=40%, ≤3000=35%, else 30%."""
    bua_sqft = lookup(ctx["request"], "existing_bua_sqft")
    if bua_sqft is None:
        raise MissingData("existing_bua_sqft")
    bua_sqm = float(bua_sqft) / SQM_TO_SQFT
    if bua_sqm <= 500:
        return 0.50
    if bua_sqm <= 1000:
        return 0.45
    if bua_sqm <= 2000:
        return 0.40
    if bua_sqm <= 3000:
        return 0.35
    return 0.30


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
        return 0

    try:
        pct_val = float(pct) / 100.0
        return f"={total_fsi_cell} * {pct_val}"
    except (ValueError, TypeError):
        return 0


@register("dcpr_parking_for_sale")
def dcpr_parking_for_sale(ctx, **kwargs) -> int:
    """
    DCPR 2034 car parking → cars for sale (C30).

    Total BUA (sqft, from OCR) → sqm
    Commercial area = BUA × 15%  → commercial parking = commercial_sqm / 37.5
    Residential area = BUA × 85% → num_homes = floor(residential_sqm / 90)
                                 → residential parking = num_homes × 2
    Base = residential + commercial
    Total = round(base × 1.10)   (+10% visitor, standard round)
    C30   = ceil(total / 2)      (half for sale)
    """
    import math

    req = ctx["request"]

    total_bua_sqft = lookup(req, "existing_bua_sqft") or 0
    if not total_bua_sqft:
        raise MissingData("existing_bua_sqft")

    total_bua_sqm = float(total_bua_sqft) / SQM_TO_SQFT
    commercial_sqm = total_bua_sqm * 0.15
    residential_sqm = total_bua_sqm * 0.85

    num_homes = math.floor(residential_sqm / 90)
    residential_parking = num_homes * 2
    commercial_parking = commercial_sqm / 37.5

    base = residential_parking + commercial_parking
    total = round(base * 1.10)  # +10% visitor, round to nearest int
    return max(1, math.ceil(total / 2))


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
