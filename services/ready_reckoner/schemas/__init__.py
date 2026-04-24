from pydantic import BaseModel, Field
from typing import List, Optional


class PremiumLineItem(BaseModel):
    description: str
    basis: str
    rate: float
    area_or_units: float
    amount: float


class LocationInfo(BaseModel):
    district: str
    taluka: str
    locality: str
    village: str
    zone: str
    sub_zone: str
    cts_no: str


class AdministrativeInfo(BaseModel):
    type_of_area: str
    local_body_name: str
    local_body_type: str


class ApplicabilityInfo(BaseModel):
    commence_from: str
    commence_to: str
    landmark_note: str


class RRRateItem(BaseModel):
    category: str
    value: float
    previous_year_rate: float
    increase_amount: float
    increase_or_decrease_percent: float


class PremiumRequest(BaseModel):
    scheme: str = "33(7)"

    # Location — use locality (primary) + zone to identify the RR zone
    district: str = "mumbai"
    taluka: str = "mumbai-city"
    locality: str = "bhuleshwar"   # e.g. "bhuleshwar", "bhandup", "vile-parle-east"
    zone: str = "5"                 # zone number as in data (may be compound like "5/43")
    sub_zone: str = ""              # optional; only ~111 records have it

    property_type: str = "residential"  # "residential", "commercial", "open_land"
    property_area_sqm: float = 0.0
    plot_area_sqm: float = 0.0

    # RR Rate overrides (leave None to auto-resolve from matched record)
    rr_open_land_sqm: Optional[float] = None
    rr_residential_sqm: Optional[float] = None

    # Buildable area inputs
    permissible_bua_sqft: float = 0.0
    residential_bua_sqft: float = 0.0
    commercial_bua_sqft: float = 0.0

    # Fungible / TDR areas (sqft)
    fungible_residential_sqft: float = 0.0
    fungible_commercial_sqft: float = 0.0
    staircase_area_sqft: float = 0.0
    general_tdr_area_sqft: float = 0.0
    slum_tdr_area_sqft: float = 0.0

    # Adjustments
    amenities_premium_percentage: float = 0.0
    depreciation_percentage: float = 0.0

    # DCPR ratios (Mumbai defaults)
    premium_fsi_ratio: float = 0.50
    fungible_res_ratio: float = 0.35
    fungible_comm_ratio: float = 0.35
    staircase_ratio: float = 0.25

    # MCGM fee rates
    scrutiny_fee_sqft: float = 5.0
    dev_charge_sqm: float = 100.0
    luc_charge_sqm: float = 50.0


class PremiumResponse(BaseModel):
    scheme: str

    # Matched RR record details
    matched_location: LocationInfo
    administrative: AdministrativeInfo
    applicability: ApplicabilityInfo
    rr_rates: List[RRRateItem]

    # Calculation output
    line_items: List[PremiumLineItem]
    total_property_value: float
    total_fsi_tdr_premiums: float
    total_mcgm_charges: float
    grand_total: float
    grand_total_crore: float

