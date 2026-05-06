"""NOC flag calcs — convert DP-report NOC requirements into 0/1 toggles."""

from __future__ import annotations

from ..calc_registry import register


@register("noc_flag_from_dp")
def noc_flag_from_dp(ctx, noc_type: str) -> int:
    """Return 1 if the given NOC type is listed as required in dp_report, else 0.

    Expects ``ctx["request"]["dp_report"]["required_nocs"]`` to be a list of
    strings (case-insensitive match).
    """
    required = (ctx["request"].get("dp_report") or {}).get("required_nocs") or []
    target = noc_type.lower().strip()
    for n in required:
        if isinstance(n, str) and n.lower().strip() == target:
            return 1
    return 0
