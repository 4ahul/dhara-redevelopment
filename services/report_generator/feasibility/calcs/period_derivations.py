"""Period/duration derivations."""

from __future__ import annotations

import math

from ..calc_registry import register
from ..exceptions import MissingData


@register("completion_months_from_area")
def completion_months_from_area(
    ctx, area_name: str, rate_sqft_per_month: float, minimum: int = 0
) -> int:
    a = ctx["resolved"].get(area_name)
    if a is None:
        raise MissingData(area_name)
    months = int(math.ceil(float(a) / float(rate_sqft_per_month)))
    return max(months, int(minimum))


@register("completion_months_from_height")
def completion_months_from_height(ctx) -> int:
    """O55/Q55: Completion months from permissible height. Floors=height/3; ≤9=18m, ≤20=36m, else 48m."""
    h = (ctx["request"].get("dp_report") or {}).get("height_limit_m") or (
        ctx["request"].get("height") or {}
    ).get("max_height_m")
    if h is None:
        raise MissingData("dp_report.height_limit_m or height.max_height_m")
    floors = math.floor(float(h) / 3.0)
    if floors <= 9:
        return 18
    if floors <= 20:
        return 36
    return 48
