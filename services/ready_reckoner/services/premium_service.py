import logging

from ..repositories.rr_repository import rr_repository
from ..schemas import (
    AdministrativeInfo,
    ApplicabilityInfo,
    LocationInfo,
    PremiumLineItem,
    PremiumRequest,
    PremiumResponse,
    RRRateItem,
)

logger = logging.getLogger(__name__)

# Fallback when a rate category is missing from the matched record
_FALLBACK_LAND_RATE = 199670


def _extract_rates(record: dict) -> dict[str, float]:
    """Return {category_lower: value} from the matched record's rates list."""
    return {
        r["category"].lower(): float(r["value"])
        for r in record.get("rates", [])
        if r.get("value") is not None
    }


def _build_location(record: dict, req: PremiumRequest) -> LocationInfo:
    loc = record.get("location", {})
    return LocationInfo(
        district=loc.get("district", req.district),
        taluka=loc.get("taluka", req.taluka),
        locality=loc.get("locality", req.locality),
        village=loc.get("village", ""),
        zone=str(loc.get("zone", req.zone)),
        sub_zone=str(loc.get("sub_zone", req.sub_zone)),
        cts_no=loc.get("cts_no", ""),
    )


def _build_administrative(record: dict) -> AdministrativeInfo:
    adm = record.get("administrative", {})
    return AdministrativeInfo(
        type_of_area=adm.get("type_of_area", ""),
        local_body_name=adm.get("local_body_name", ""),
        local_body_type=adm.get("local_body_type", ""),
    )


def _build_applicability(record: dict) -> ApplicabilityInfo:
    app = record.get("applicability", {})
    return ApplicabilityInfo(
        commence_from=app.get("commence_from", ""),
        commence_to=app.get("commence_to", ""),
        landmark_note=app.get("landmark_note", ""),
    )


def _build_rr_rates(record: dict) -> list[RRRateItem]:
    return [
        RRRateItem(
            category=r.get("category", ""),
            value=float(r.get("value", 0)),
            previous_year_rate=float(r.get("previous_year_rate", 0)),
            increase_amount=float(r.get("increase_amount", 0)),
            increase_or_decrease_percent=float(r.get("increase_or_decrease_percent", 0.0)),
        )
        for r in record.get("rates", [])
    ]


class PremiumService:
    @staticmethod
    async def calculate_premiums(req: PremiumRequest) -> PremiumResponse:
        """Calculate property value and all government premiums based on DCPR 2034."""

        record = await rr_repository.get_rates(
            district=req.district,
            taluka=req.taluka,
            locality=req.locality,
            zone=req.zone,
            sub_zone=req.sub_zone,
        )

        rates = _extract_rates(record)

        # Resolve effective RR rates (caller override → matched record → fallback)
        rr_open = req.rr_open_land_sqm or rates.get("land", _FALLBACK_LAND_RATE)
        rr_res = req.rr_residential_sqm or rates.get("residential", rr_open)
        rr_comm = rates.get("shop", rates.get("office", rr_open * 1.5))

        line_items: list[PremiumLineItem] = []

        # ------------------------------------------------------------------ #
        # 1. Property Valuation                                               #
        # ------------------------------------------------------------------ #
        pt = req.property_type.lower()
        if pt == "commercial":
            base_rr_rate = rr_comm
        elif pt == "open_land":
            base_rr_rate = rr_open
        else:
            base_rr_rate = rr_res

        total_property_value = 0.0

        if req.property_area_sqm > 0:
            base_value = base_rr_rate * req.property_area_sqm
            amenities = base_value * (req.amenities_premium_percentage / 100.0)
            depreciation = base_value * (req.depreciation_percentage / 100.0)
            total_property_value = base_value + amenities - depreciation

            line_items.append(
                PremiumLineItem(
                    description=f"Property Base Value ({req.property_type.title()})",
                    basis=f"@ Rs.{base_rr_rate:,.2f}/sqm × {req.property_area_sqm:,.2f} sqm",
                    rate=base_rr_rate,
                    area_or_units=req.property_area_sqm,
                    amount=base_value,
                )
            )
            if amenities:
                line_items.append(
                    PremiumLineItem(
                        description=f"Amenities Premium ({req.amenities_premium_percentage}%)",
                        basis=f"@ {req.amenities_premium_percentage}% of Base Value",
                        rate=req.amenities_premium_percentage,
                        area_or_units=base_value,
                        amount=amenities,
                    )
                )
            if depreciation:
                line_items.append(
                    PremiumLineItem(
                        description=f"Depreciation ({req.depreciation_percentage}%)",
                        basis=f"@ {req.depreciation_percentage}% of Base Value",
                        rate=req.depreciation_percentage,
                        area_or_units=base_value,
                        amount=-depreciation,
                    )
                )
            line_items.append(
                PremiumLineItem(
                    description="Total Property Value (Ready Reckoner)",
                    basis="Base Value + Amenities Premium − Depreciation",
                    rate=0.0,
                    area_or_units=req.property_area_sqm,
                    amount=total_property_value,
                )
            )

        # ------------------------------------------------------------------ #
        # 2. FSI / TDR Premiums (DCPR 2034)                                  #
        # ------------------------------------------------------------------ #
        _VALUATION_LABELS = {
            "Total Property Value (Ready Reckoner)",
        }
        _VALUATION_PREFIXES = ("Property Base Value", "Amenities Premium", "Depreciation")

        if req.permissible_bua_sqft > 0:
            bua_sqm = req.permissible_bua_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="Additional FSI Premium",
                    basis=f"@ {req.premium_fsi_ratio * 100:.0f}% of RR Land × {bua_sqm:.2f} sqm",
                    rate=rr_open * req.premium_fsi_ratio,
                    area_or_units=bua_sqm,
                    amount=rr_open * req.premium_fsi_ratio * bua_sqm,
                )
            )

        if req.fungible_residential_sqft > 0:
            sqm = req.fungible_residential_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="Fungible Compensatory Area - Residential",
                    basis=f"@ {req.fungible_res_ratio * 100:.0f}% of RR Land × {sqm:.2f} sqm",
                    rate=rr_open * req.fungible_res_ratio,
                    area_or_units=sqm,
                    amount=rr_open * req.fungible_res_ratio * sqm,
                )
            )

        if req.fungible_commercial_sqft > 0:
            sqm = req.fungible_commercial_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="Fungible Compensatory Area - Commercial",
                    basis=f"@ {req.fungible_comm_ratio * 100:.0f}% of RR Land × {sqm:.2f} sqm",
                    rate=rr_open * req.fungible_comm_ratio,
                    area_or_units=sqm,
                    amount=rr_open * req.fungible_comm_ratio * sqm,
                )
            )

        if req.staircase_area_sqft > 0:
            sqm = req.staircase_area_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="Staircase Premium",
                    basis=f"@ {req.staircase_ratio * 100:.0f}% of RR Residential × {sqm:.2f} sqm",
                    rate=rr_res * req.staircase_ratio,
                    area_or_units=sqm,
                    amount=rr_res * req.staircase_ratio * sqm,
                )
            )

        if req.general_tdr_area_sqft > 0:
            sqm = req.general_tdr_area_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="General TDR",
                    basis=f"@ 50% of RR Land × {sqm:.2f} sqm",
                    rate=rr_open * 0.50,
                    area_or_units=sqm,
                    amount=rr_open * 0.50 * sqm,
                )
            )

        if req.slum_tdr_area_sqft > 0:
            sqm = req.slum_tdr_area_sqft / 10.764
            line_items.append(
                PremiumLineItem(
                    description="Slum TDR",
                    basis=f"@ 35% of RR Land × {sqm:.2f} sqm",
                    rate=rr_open * 0.35,
                    area_or_units=sqm,
                    amount=rr_open * 0.35 * sqm,
                )
            )

        total_fsi_tdr = sum(
            item.amount
            for item in line_items
            if item.description not in _VALUATION_LABELS
            and not any(item.description.startswith(p) for p in _VALUATION_PREFIXES)
        )

        # ------------------------------------------------------------------ #
        # 3. MCGM Charges & Fees                                             #
        # ------------------------------------------------------------------ #
        total_bua = (req.commercial_bua_sqft or 0) + (req.residential_bua_sqft or 0)

        if total_bua > 0:
            line_items.append(
                PremiumLineItem(
                    description="Scrutiny / Amended Plan Fees",
                    basis=f"@ Rs.{req.scrutiny_fee_sqft}/sqft × {total_bua} sqft",
                    rate=req.scrutiny_fee_sqft,
                    area_or_units=total_bua,
                    amount=total_bua * req.scrutiny_fee_sqft,
                )
            )
            line_items.append(
                PremiumLineItem(
                    description="Development Cess",
                    basis=f"@ Rs.5/sqft × {total_bua} sqft",
                    rate=5,
                    area_or_units=total_bua,
                    amount=total_bua * 5,
                )
            )
            line_items.append(
                PremiumLineItem(
                    description="CFO Scrutiny Fees",
                    basis=f"@ Rs.3/sqft × {total_bua} sqft",
                    rate=3,
                    area_or_units=total_bua,
                    amount=total_bua * 3,
                )
            )
            line_items.append(
                PremiumLineItem(
                    description="Incidental, Miscellaneous, Contingencies",
                    basis=f"@ Rs.10/sqft × {total_bua} sqft",
                    rate=10,
                    area_or_units=total_bua,
                    amount=total_bua * 10,
                )
            )

        if req.plot_area_sqm > 0:
            line_items.append(
                PremiumLineItem(
                    description="Development Charges (MCGM)",
                    basis=f"@ Rs.{req.dev_charge_sqm}/sqm × {req.plot_area_sqm:.2f} sqm",
                    rate=req.dev_charge_sqm,
                    area_or_units=req.plot_area_sqm,
                    amount=req.plot_area_sqm * req.dev_charge_sqm,
                )
            )
            line_items.append(
                PremiumLineItem(
                    description="Land Under Construction (LUC) Charges",
                    basis=f"@ Rs.{req.luc_charge_sqm}/sqm × {req.plot_area_sqm:.2f} sqm",
                    rate=req.luc_charge_sqm,
                    area_or_units=req.plot_area_sqm,
                    amount=req.plot_area_sqm * req.luc_charge_sqm,
                )
            )

        _MCGM_LABELS = {
            "Scrutiny / Amended Plan Fees",
            "Development Charges (MCGM)",
            "Development Cess",
            "CFO Scrutiny Fees",
            "Land Under Construction (LUC) Charges",
            "Incidental, Miscellaneous, Contingencies",
        }
        total_mcgm = sum(item.amount for item in line_items if item.description in _MCGM_LABELS)

        grand_total = total_fsi_tdr + total_mcgm

        return PremiumResponse(
            scheme=req.scheme,
            matched_location=_build_location(record, req),
            administrative=_build_administrative(record),
            applicability=_build_applicability(record),
            rr_rates=_build_rr_rates(record),
            line_items=line_items,
            total_property_value=total_property_value,
            total_fsi_tdr_premiums=total_fsi_tdr,
            total_mcgm_charges=total_mcgm,
            grand_total=grand_total,
            grand_total_crore=grand_total / 10_000_000,
        )


premium_service = PremiumService()
