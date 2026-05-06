"""Height derivations — floor counts, podium allowance by plot area."""

from __future__ import annotations

import math

from ..calc_registry import register
from ..exceptions import MissingData


def _permissible_height(ctx) -> float:
    """Resolve permissible height: DP zone limit → aviation max."""
    h = (ctx["request"].get("dp_report") or {}).get("height_limit_m") or (
        ctx["request"].get("height") or {}
    ).get("max_height_m")
    if h is None:
        raise MissingData("dp_report.height_limit_m or height.max_height_m")
    return float(h)


def _plot_area(ctx) -> float:
    a = ctx["request"].get("plot_area_sqm")
    if a is None:
        raise MissingData("plot_area_sqm")
    return float(a)


@register("floors_from_max_height")
def floors_from_max_height(ctx, floor_height_m: float) -> int:
    h = (ctx["request"].get("height") or {}).get("max_height_m")
    if h is None:
        raise MissingData("height.max_height_m")
    return math.floor(float(h) / float(floor_height_m))


@register("podium_count_from_plot_area")
def podium_count_from_plot_area(ctx) -> int:
    a = _plot_area(ctx)
    if a < 1000:
        return 0
    if a < 2500:
        return 1
    if a < 5000:
        return 2
    return 3


@register("osd_ratio_from_height")
def osd_ratio_from_height(ctx) -> float:
    """N63: OSD % based on permissible height — ≤32m=18%, ≤70m=25%, else 30%."""
    h = _permissible_height(ctx)
    if h <= 32:
        return 0.18
    if h <= 70:
        return 0.25
    return 0.30


@register("construction_rate_from_height")
def construction_rate_from_height(ctx) -> float:
    """O64: Construction area multiplier — ≤32m=1.40, ≤70m=1.50, else 1.70."""
    h = _permissible_height(ctx)
    if h <= 32:
        return 1.40
    if h <= 70:
        return 1.50
    return 1.70


@register("podium_ratio_from_plot")
def podium_ratio_from_plot(ctx) -> float:
    """N65: Podium const area ratio — ≤1000=0, ≤2500=60%, ≤5000=40%, else 20%."""
    a = _plot_area(ctx)
    if a <= 1000:
        return 0.0
    if a <= 2500:
        return 0.60
    if a <= 5000:
        return 0.40
    return 0.20


@register("basement_count_from_plot")
def basement_count_from_plot(ctx) -> int:
    """O65: Basement count — ≤1000=0; else 2 if height>57.13, else 0."""
    a = _plot_area(ctx)
    if a <= 1000:
        return 0
    try:
        h = _permissible_height(ctx)
    except MissingData:
        return 0
    return 2 if h > 57.13 else 0


@register("basement_ratio_from_plot")
def basement_ratio_from_plot(ctx) -> float:
    """N66: Basement const area % if basementRequired Yes — ≤1000=70%, ≤2500=60%, ≤5000=40%, else 20%."""
    req_val = (ctx["request"].get("manual_inputs") or {}).get("basementRequired")
    if not req_val or str(req_val).lower() in ("false", "0", "no", "n"):
        return 0.0
    a = _plot_area(ctx)
    if a <= 1000:
        return 0.70
    if a <= 2500:
        return 0.60
    if a <= 5000:
        return 0.40
    return 0.20


@register("basement_floors_from_plot")
def basement_floors_from_plot(ctx) -> int:
    """O66: Basement floor count if basementRequired Yes — ≤1000=3, ≤2500=2, else 1."""
    req_val = (ctx["request"].get("manual_inputs") or {}).get("basementRequired")
    if not req_val or str(req_val).lower() in ("false", "0", "no", "n"):
        return 0
    a = _plot_area(ctx)
    if a <= 1000:
        return 3
    if a <= 2500:
        return 2
    return 1
