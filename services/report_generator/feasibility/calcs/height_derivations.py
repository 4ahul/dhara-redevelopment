"""Height derivations — floor counts, podium allowance by plot area."""

from __future__ import annotations

import math
from ..calc_registry import register
from ..exceptions import MissingData


@register("floors_from_max_height")
def floors_from_max_height(ctx, floor_height_m: float) -> int:
    h = (ctx["request"].get("height") or {}).get("max_height_m")
    if h is None:
        raise MissingData("height.max_height_m")
    return int(math.floor(float(h) / float(floor_height_m)))


@register("podium_count_from_plot_area")
def podium_count_from_plot_area(ctx) -> int:
    a = ctx["request"].get("plot_area_sqm")
    if a is None:
        raise MissingData("plot_area_sqm")
    a = float(a)
    if a < 1000:
        return 0
    if a < 2500:
        return 1
    if a < 5000:
        return 2
    return 3
