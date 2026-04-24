"""
Data Normalizer — Report Generator
Converts the flat LLM-assembled dict into the per-scheme nested structure
that pdf_builder and excel_builder expect.

Both builders index data as:
    fsi["33(7)(B)"]["zonal_fsi"]
    bua["33(7)(B)"]["total_bua_sqft"]
    financial["33(7)(B)"]["const_total"]
    additional_entitlement["33(7)(B)"]["profit_crore"]

The LLM passes a flat dict.  This module bridges the gap using
DCPR 2034 rules to fill all four schemes.
"""

from __future__ import annotations

from services.report_generator.core.config import settings

SCHEMES = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

# ── DCPR 2034 FSI constants ──────────────────────────────────────────────────
# add_premium and tdr depend on road width (≥18 m for max values)
_FSI_RULES: dict[str, dict] = {
    "33(7)(B)":  {"add_premium_18": 0.84, "add_premium_9": 0.50, "tdr": 0.83, "bonus_2020b": 0.0},
    "33(20)(B)": {"add_premium_18": 0.84, "add_premium_9": 0.50, "tdr": 0.83, "bonus_2020b": 1.00},
    "33(11)":    {"add_premium_18": 0.0,  "add_premium_9": 0.0,  "tdr": 0.0,  "bonus_2020b": 0.0},
    "33(12)(B)": {"add_premium_18": 0.84, "add_premium_9": 0.50, "tdr": 0.83, "bonus_2020b": 0.0},
}

# Additional RERA % available for sale per scheme
_ADD_RERA_PCT: dict[str, float] = {
    "33(7)(B)":  0.35,
    "33(20)(B)": 0.50,
    "33(11)":    0.30,
    "33(12)(B)": 0.40,
}

# Standard rates from settings
CONST_RATE_PER_SQFT   = settings.CONST_RATE_PER_SQFT
PROF_FEE_PER_SQFT     = settings.PROF_FEE_PER_SQFT
CORPUS_PER_SQFT       = settings.CORPUS_PER_SQFT
TEMP_RESI_Y1_SQFT     = settings.TEMP_RESI_Y1_SQFT
TEMP_COMM_Y1_SQFT     = settings.TEMP_COMM_Y1_SQFT

GST_MEMBER_PCT        = 0.05     # GST on existing member purchase
GST_ON_CONSTRUCTION   = 0.18     # 18% GST on construction cost
STAMP_DUTY_PCT        = 0.06     # 6% stamp duty on development agreement value
ZONAL_FSI             = settings.ZONAL_FSI
FUNGIBLE_RATIO        = 0.35     # 35% fungible compensatory area
SQFT_PER_SQM          = 10.764   # 1 sqm = 10.764 sqft
PARKING_SQFT_PER_SLOT = 450      # 1 parking per 450 sqft BUA
STAIRCASE_RATIO       = 0.135    # ~13.5% of BUA for stairs/lobbies/lift
AMENITY_RATIO         = 0.018    # ~1.8% of BUA for yogalaya/fitness/amenities



# ── Premium line-item keyword mapping ────────────────────────────────────────
# Maps premium_checker line_item descriptions (partial match) → financial key
_PREMIUM_KEY_MAP = {
    "Additional FSI Premium": "add_fsi_premium",
    "Fungible Compensatory Area": "fungible_res",
    "Staircase": "staircase_prem",
    "Open Space Deficiency": "osd_premium",
    "Slum TDR": "slum_tdr",
    "General TDR": "general_tdr",
    "Scrutiny": "scrutiny",
    "Development Charges": "dev_charges",
    "Development Cess": "dev_cess",
    "LUC": "luc",
    "CFO": "cfo",
    "Heritage": "heritage",
    "Miscellaneous": "misc",
}


def _extract_premium_amounts(line_items: list[dict]) -> dict[str, float]:
    """Map premium_checker line items to financial dict keys."""
    out: dict[str, float] = {}
    for item in line_items:
        desc = item.get("description", "")
        amount = float(item.get("amount", 0) or 0)
        for keyword, key in _PREMIUM_KEY_MAP.items():
            if keyword.lower() in desc.lower():
                out[key] = out.get(key, 0) + amount
                break
    return out


def _fsi_for_scheme(scheme: str, road_width_m: float) -> dict:
    """Compute FSI breakdown dict for a single scheme."""
    rules = _FSI_RULES[scheme]
    add_prem = rules["add_premium_18"] if road_width_m >= 18 else rules["add_premium_9"]
    tdr = rules["tdr"]
    bonus = rules["bonus_2020b"]

    zonal = ZONAL_FSI
    fsi_ptc = round(zonal + add_prem + tdr, 2)         # pre-bonus, pre-fungible
    total_fsi = round(fsi_ptc + bonus, 2)
    fungible = round(total_fsi * FUNGIBLE_RATIO, 2)
    total_perm = round(total_fsi + fungible, 2)

    return {
        "plot_area":            None,   # filled in caller (same for all schemes)
        "road_width":           road_width_m,
        "zonal_fsi":            zonal,
        "add_fsi_premium":      add_prem,
        "tdr_road_width":       tdr,
        "fsi_ptc":              fsi_ptc,
        "add_fsi_2020b":        bonus if bonus else None,
        "total_fsi":            total_fsi,
        "fungible":             fungible,
        "total_fsi_permissible": total_perm,
    }


def _bua_for_scheme(scheme: str, fsi_dict: dict, plot_sqm: float) -> dict:
    """Compute BUA breakdown dict for a single scheme."""
    plot_sqft = plot_sqm * SQFT_PER_SQM
    total_perm = fsi_dict["total_fsi_permissible"]

    total_bua    = round(plot_sqft * total_perm)
    rera_carpet  = round(total_bua * 0.90)
    add_fsi_sqft = round(plot_sqft * fsi_dict["add_fsi_premium"])
    tdr_sqft     = round(plot_sqft * fsi_dict["tdr_road_width"])
    stair_sqft   = round(total_bua * STAIRCASE_RATIO)
    amenity_sqft = round(total_bua * AMENITY_RATIO)
    constr_sqft  = total_bua + stair_sqft + amenity_sqft
    parking      = int(total_bua / PARKING_SQFT_PER_SLOT)
    fungible_sqm = round(plot_sqm * fsi_dict["fungible"], 2)

    return {
        "total_bua_sqft":     total_bua,
        "rera_carpet_sqft":   rera_carpet,
        "add_fsi_sqft":       add_fsi_sqft,
        "tdr_sqft":           tdr_sqft,
        "staircase_sqft":     stair_sqft,
        "yogalaya_sqft":      amenity_sqft,
        "total_constr_sqft":  constr_sqft,
        "fungible_total_sqm": fungible_sqm,
        "parking":            parking,
    }


def _financial_for_scheme(
    scheme: str,
    bua: dict,
    plot_sqm: float,
    premium_amounts: dict[str, float],
    premium_data: dict,
    existing_carpet_sqft: float,
    sale_rate: float,
    rr_open_land: float,
) -> dict:
    """Compute financial dict for a single scheme."""
    total_bua = bua["total_bua_sqft"]
    add_fsi_sqft = bua["add_fsi_sqft"]

    # 1. Construction
    const_total    = round(total_bua * CONST_RATE_PER_SQFT)
    parking_cost   = round(const_total * 0.60)
    const_subtotal = const_total + parking_cost
    gst_const      = round(const_subtotal * GST_ON_CONSTRUCTION)
    const_with_gst = const_subtotal + gst_const

    # 2. FSI / TDR premiums — use premium_checker amounts if available
    # Prefer actual amounts from the premium_checker response for the matched scheme
    fsi_tdr_line_total = premium_data.get("total_fsi_tdr_premiums", 0)
    add_fsi_prem_amt   = premium_amounts.get("add_fsi_premium", round(add_fsi_sqft / SQFT_PER_SQM * rr_open_land * 0.50))
    fungible_res_amt   = premium_amounts.get("fungible_res",     round(bua["fungible_total_sqm"] * rr_open_land * 0.35))
    staircase_prem_amt = premium_amounts.get("staircase_prem",   round(bua["staircase_sqft"] / SQFT_PER_SQM * rr_open_land * 0.25))
    osd_prem_amt       = premium_amounts.get("osd_premium",       0)
    slum_tdr_amt       = premium_amounts.get("slum_tdr",          0)
    general_tdr_amt    = premium_amounts.get("general_tdr",       0)
    fsi_tdr_total      = (
        fsi_tdr_line_total or
        (add_fsi_prem_amt + fungible_res_amt + staircase_prem_amt + osd_prem_amt + slum_tdr_amt + general_tdr_amt)
    )

    # 3. MCGM charges
    mcgm_line_total = premium_data.get("total_mcgm_charges", 0)
    scrutiny    = premium_amounts.get("scrutiny",     round(total_bua * 5))
    dev_charges = premium_amounts.get("dev_charges",  round(plot_sqm * 100))
    dev_cess    = premium_amounts.get("dev_cess",     round(plot_sqm * 30))
    luc         = premium_amounts.get("luc",          round(plot_sqm * 50))
    cfo         = premium_amounts.get("cfo",          round(total_bua * 2))
    heritage    = premium_amounts.get("heritage",     0)
    misc        = premium_amounts.get("misc",         round(const_with_gst * 0.02))
    mcgm_total  = mcgm_line_total or (scrutiny + dev_charges + dev_cess + luc + cfo + heritage + misc)

    # 4. Professional fees
    prof_fees = round(total_bua * PROF_FEE_PER_SQFT)

    # 5. Temporary alternate accommodation (36 months, escalating 10%/yr)
    temp_comm_y1 = round(bua.get("add_fsi_sqft", 0) * TEMP_COMM_Y1_SQFT)
    temp_res_y1  = round(existing_carpet_sqft * TEMP_RESI_Y1_SQFT)
    temp_res_y2  = round(temp_res_y1 * 1.10)
    temp_res_y3  = round(temp_res_y1 * 1.20)
    temp_total   = temp_comm_y1 + temp_res_y1 + temp_res_y2 + temp_res_y3

    # 6. Stamp duty & registration
    dev_agreement_value = total_bua * sale_rate
    stamp_duty  = round(dev_agreement_value * STAMP_DUTY_PCT)
    stamp_total = stamp_duty   # simplified; registration folded in

    # 7. Project total
    project_total = const_with_gst + fsi_tdr_total + mcgm_total + prof_fees + temp_total + stamp_total

    # 8. Corpus fund
    corpus = round(existing_carpet_sqft * CORPUS_PER_SQFT)

    # 9. Grand total
    redevelopment_total = project_total + corpus

    return {
        "const_total":        const_total,
        "parking_cost":       parking_cost,
        "const_subtotal":     const_subtotal,
        "gst":                gst_const,
        "const_with_gst":     const_with_gst,
        "add_fsi_premium":    add_fsi_prem_amt,
        "fungible_res":       fungible_res_amt,
        "staircase_prem":     staircase_prem_amt,
        "osd_premium":        osd_prem_amt,
        "slum_tdr":           slum_tdr_amt,
        "general_tdr":        general_tdr_amt,
        "fsi_tdr_total":      fsi_tdr_total,
        "scrutiny":           scrutiny,
        "dev_charges":        dev_charges,
        "dev_cess":           dev_cess,
        "luc":                luc,
        "cfo":                cfo,
        "heritage":           heritage,
        "misc":               misc,
        "mcgm_total":         mcgm_total,
        "prof_fees":          prof_fees,
        "temp_comm_y1":       temp_comm_y1,
        "temp_res_y1":        temp_res_y1,
        "temp_res_y2":        temp_res_y2,
        "temp_res_y3":        temp_res_y3,
        "temp_total":         temp_total,
        "stamp_duty":         stamp_duty,
        "stamp_total":        stamp_total,
        "project_total":      project_total,
        "corpus":             corpus,
        "redevelopment_total": redevelopment_total,
    }


def _additional_entitlement(
    scheme: str,
    bua: dict,
    fin: dict,
    existing_carpet_sqft: float,
    sale_rate: float,
) -> dict:
    rera_total_sqft = bua["rera_carpet_sqft"]
    add_pct         = _ADD_RERA_PCT[scheme]
    # Area available for free sale = total RERA - what members need (existing × (1+add_pct))
    member_need     = existing_carpet_sqft * (1 + add_pct)
    sale_area_sqft  = max(0.0, rera_total_sqft - member_need)
    add_area_sqft   = sale_area_sqft   # simplification: all extra is sale area

    revenue_crore = round(sale_area_sqft * sale_rate / 1e7, 2)
    cost_crore    = round(fin["redevelopment_total"] / 1e7, 2)
    gst_crore     = round(existing_carpet_sqft * sale_rate * GST_MEMBER_PCT / 1e7, 2)
    profit_crore  = round(revenue_crore - cost_crore - gst_crore, 2)
    profit_pct    = round(profit_crore / cost_crore, 4) if cost_crore else 0.0

    return {
        "cost_crore":      cost_crore,
        "rera_total_sqft": rera_total_sqft,
        "existing_sqft":   existing_carpet_sqft,
        "sale_rate":       sale_rate,
        "add_rera_pct":    add_pct,
        "add_area_sqft":   add_area_sqft,
        "sale_area_sqft":  sale_area_sqft,
        "revenue_crore":   revenue_crore,
        "gst_crore":       gst_crore,
        "profit_crore":    profit_crore,
        "profit_pct":      profit_pct,
    }


# ── Public entry point ────────────────────────────────────────────────────────

def normalize_report_data(raw: dict) -> dict:
    """
    Takes the flat LLM-assembled ReportRequest dict and returns the full nested
    structure that pdf_builder.build_feasibility_pdf() and
    excel_builder.build_feasibility_report() expect.

    Preserves all original keys; adds/replaces:
        fsi, bua, financial, additional_entitlement
    """
    plot_sqm     = float(raw.get("plot_area_sqm") or 0)
    road_width   = float(raw.get("road_width_m") or 9)   # default 9 m if missing

    # Existing carpet area from residential_units (or num_flats heuristic)
    res_units: list[dict] = raw.get("residential_units", [])
    if res_units:
        existing_carpet_sqft = sum(
            float(u.get("total_sqft", u.get("area_sqm", 0) * SQFT_PER_SQM))
            for u in res_units
        )
    else:
        # Rough fallback: assume 500 sqft per flat
        existing_carpet_sqft = float(raw.get("num_flats", 0)) * 500.0

    # Sale rate — try the financial sub-dict first (LLM flat key), then raw
    flat_fin = raw.get("financial", {}) if isinstance(raw.get("financial"), dict) else {}
    sale_rate = float(
        flat_fin.get("sale_rate_sqft")
        or raw.get("sale_rate_sqft")
        or 65_000
    )

    # Premium checker response (may be empty if service failed)
    premium_data  = raw.get("premium", {}) if isinstance(raw.get("premium"), dict) else {}
    line_items    = premium_data.get("line_items", []) or []
    premium_amts  = _extract_premium_amounts(line_items)

    # RR open land rate (used as fallback for FSI premium calculation)
    rr_section = premium_data.get("rr_data", {}) or premium_data.get("ready_reckoner", {}) or {}
    rr_open_land = float(rr_section.get("rr_open_land_sqm", 0) or raw.get("ready_reckoner", {}).get("rr_open_land_sqm", 200_000))

    # ── Build per-scheme dicts ────────────────────────────────────────────────
    fsi_out: dict  = {}
    bua_out: dict  = {}
    fin_out: dict  = {}
    ae_out:  dict  = {}

    for scheme in SCHEMES:
        fsi_d = _fsi_for_scheme(scheme, road_width)
        fsi_d["plot_area"] = plot_sqm          # same for all schemes
        bua_d = _bua_for_scheme(scheme, fsi_d, plot_sqm)
        fin_d = _financial_for_scheme(
            scheme, bua_d, plot_sqm,
            premium_amts, premium_data,
            existing_carpet_sqft, sale_rate, rr_open_land,
        )
        ae_d  = _additional_entitlement(scheme, bua_d, fin_d, existing_carpet_sqft, sale_rate)

        fsi_out[scheme] = fsi_d
        bua_out[scheme] = bua_d
        fin_out[scheme] = fin_d
        ae_out[scheme]  = ae_d

    # ── Assemble output — original dict + normalized tables ───────────────────
    result = dict(raw)           # copy all original keys (site_analysis, height, dp_report, etc.)
    result["fsi"]                   = fsi_out
    result["bua"]                   = bua_out
    result["financial"]             = fin_out
    result["additional_entitlement"] = ae_out

    # Convenience: expose top-level plot_area for cover sheet
    if not result.get("plot_area_sqm") and plot_sqm:
        result["plot_area_sqm"] = plot_sqm

    return result

