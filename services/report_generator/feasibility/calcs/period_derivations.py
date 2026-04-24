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

