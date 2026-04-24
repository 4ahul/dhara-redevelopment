
from ..calc_registry import register
from ..value_resolver import lookup

@register("report_header")
def report_header(ctx, **kwargs):
    """
    Generate the dynamic header for the report.
    Example: MAHESHWAR MANSION CHS Ltd /33(7)(B)  F.P no 63 of TPS-VI Vileparle
    """
    society_name = lookup(ctx["request"], "society_name") or "Unknown Society"
    scheme = lookup(ctx["request"], "scheme") or "33(7)(B)"
    fp_no = lookup(ctx["request"], "fp_no") or lookup(ctx["request"], "mcgm_property.fp_no")
    cts_no = lookup(ctx["request"], "cts_no") or lookup(ctx["request"], "mcgm_property.cts_no")
    tps_name = lookup(ctx["request"], "tps_name") or lookup(ctx["request"], "mcgm_property.tps_name")
    village = lookup(ctx["request"], "village") or lookup(ctx["request"], "mcgm_property.village")
    
    parts = [f"{society_name} /{scheme}"]
    
    if fp_no:
        fp_part = f"F.P no {fp_no}"
        if tps_name:
            fp_part += f" of {tps_name}"
        if village:
            fp_part += f" {village}"
        parts.append(fp_part)
    elif cts_no:
        cts_part = f"CTS no {cts_no}"
        if village:
            cts_part += f" {village}"
        parts.append(cts_part)
        
    return "  ".join(parts)

@register("label_with_value")
def label_with_value(ctx, label: str, path: str, fallback: str = ""):
    """Combine a static label with a dynamic value."""
    val = lookup(ctx["request"], path)
    if val is None:
        return f"{label} {fallback}"
    return f"{label} {val}"

