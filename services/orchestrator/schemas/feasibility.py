import contextlib
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated

def _coerce_society(v: Any) -> str | None:
    """Convert Society ORM object to its name, or pass through strings/None."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    # Assume it's a Society ORM object with a .name attribute
    return getattr(v, "name", None)


class FeasibilityAnalyzeResponse(BaseModel):
    """Unified response for feasibility analysis lifecycle."""

    job_id: str = Field(serialization_alias="jobId")
    status: str = "processing"
    progress: float | None = 0.0
    file_url: str | None = Field(default=None, serialization_alias="fileUrl")
    report_generated: bool | None = Field(default=False, serialization_alias="reportGenerated")
    report_error: str | None = Field(default=None, serialization_alias="reportError")

    model_config = {"populate_by_name": True}


class FeasibilityReportResponse(BaseModel):
    """Technical snapshot of a completed feasibility report."""

    id: UUID
    society_id: UUID = Field(serialization_alias="societyId")
    user_id: UUID = Field(serialization_alias="userId")
    title: str
    report_path: str | None = Field(default=None, serialization_alias="reportPath")
    file_url: str | None = Field(default=None, serialization_alias="fileUrl")
    status: str

    ward: str | None = None
    village: str | None = None
    cts_no: str | None = Field(default=None, serialization_alias="ctsNo")
    fp_no: str | None = Field(default=None, serialization_alias="fpNo")

    fsi: float | None = None
    plot_area: float | None = Field(default=None, serialization_alias="plotArea")
    estimated_value: str | None = Field(default=None, serialization_alias="estimatedValue")

    input_data: dict | None = Field(default=None, serialization_alias="inputData")
    output_data: dict | None = Field(default=None, serialization_alias="outputData")
    llm_analysis: str | None = Field(default=None, serialization_alias="aiSummary")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")

    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    society: Annotated[str | None, BeforeValidator(_coerce_society)] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class FeasibilityReportUpdate(BaseModel):
    """Metadata updates for reports."""

    title: str | None = Field(default=None, max_length=500)
    status: str | None = None
    llm_analysis: str | None = Field(default=None, alias="aiSummary")

    model_config = {"populate_by_name": True}


class FeasibilityAnalyzeRequest(BaseModel):
    """Direct JSON request for feasibility (primarily for internal/admin use)."""

    society_id: UUID = Field(alias="societyId")
    society_name: str | None = Field(default=None, alias="societyName")
    address: str | None = None
    cts_no: str | None = Field(default=None, alias="ctsNo")
    fp_no: str | None = Field(default=None, alias="fpNo")
    ward: str | None = None
    village: str | None = None

    fsi: float | None = None
    plot_area_sqm: float | None = Field(default=None, alias="plotAreaSqM")
    salable_residential_rate: float | None = Field(
        default=None, alias="salableResidentialRatePerSqFt"
    )

    model_config = {"populate_by_name": True}


class FeasibilityForm:
    """Dependency class to handle the massive multipart form submission."""

    def __init__(
        self,
        society_id: UUID,
        old_plan: UploadFile | None = File(None, alias="oldPlan"),
        tenements_sheet: UploadFile | None = File(None, alias="tenementsSheet"),
        dp_remark_pdf: UploadFile | None = File(None, alias="dpRemarkPdf"),
        land_identifier_type: str | None = Form(None, alias="landIdentifierType"),
        land_identifier_value: str | None = Form(None, alias="landIdentifierValue"),
        tps_name: str | None = Form(None, alias="tpsScheme"),
        plot_area_sqm: float | None = Form(None, alias="plotAreaSqM"),
        tenement_mode: str = Form("manual", alias="tenementMode"),
        number_of_tenements: int | None = Form(None, alias="numberOfTenements"),
        number_of_commercial_shops: int | None = Form(None, alias="numberOfCommercialShops"),
        basement_required: str | None = Form(None, alias="basementRequired"),
        corpus_commercial: float | None = Form(None, alias="corpusCommercial"),
        corpus_residential: float | None = Form(None, alias="corpusResidential"),
        bank_guarantee_commercial: float | None = Form(None, alias="bankGuranteeCommercial"),
        bank_guarantee_residential: float | None = Form(None, alias="bankGuranteeResidential"),
        sale_commercial_mun_bua_sqft: float | None = Form(None, alias="saleCommercialMunBuaSqFt"),
        commercial_area_cost_per_sqft: float | None = Form(None, alias="commercialAreaCostPerSqFt"),
        residential_area_cost_per_sqft: float | None = Form(
            None, alias="residentialAreaCostPerSqFt"
        ),
        podium_parking_cost_per_sqft: float | None = Form(None, alias="podiumParkingCostPerSqFt"),
        basement_cost_per_sqft: float | None = Form(None, alias="basementCostPerSqFt"),
        cost_acquisition_79a: float | None = Form(None, alias="costAcquisition79a"),
        salable_residential_rate: float | None = Form(None, alias="salableResidentialRatePerSqFt"),
        cars_to_sell_rate: float | None = Form(None, alias="carsToSellRatePerCar"),
        sale_area_breakup: str | None = Form(None, alias="saleAreaBreakup"),
        gf_area: float | None = Form(None, alias="saleAreaBreakup[groundFloor][area]"),
        gf_rate: float | None = Form(None, alias="saleAreaBreakup[groundFloor][rate]"),
        f1_area: float | None = Form(None, alias="saleAreaBreakup[firstFloor][area]"),
        f1_rate: float | None = Form(None, alias="saleAreaBreakup[firstFloor][rate]"),
        f2_area: float | None = Form(None, alias="saleAreaBreakup[secondFloor][area]"),
        f2_rate: float | None = Form(None, alias="saleAreaBreakup[secondFloor][rate]"),
        other_area: float | None = Form(None, alias="saleAreaBreakup[otherFloors][area]"),
        other_rate: float | None = Form(None, alias="saleAreaBreakup[otherFloors][rate]"),
        fsi: float | None = Form(None, alias="fsi"),
        zone_code: str | None = Form(None, alias="zone_code"),
    ):
        self.society_id = society_id
        self.old_plan = old_plan
        self.tenements_sheet = tenements_sheet
        self.dp_remark_pdf = dp_remark_pdf
        self.land_identifier_type = land_identifier_type
        self.land_identifier_value = land_identifier_value
        self.tps_name = tps_name
        self.plot_area_sqm = plot_area_sqm
        self.tenement_mode = tenement_mode
        self.number_of_tenements = number_of_tenements
        self.number_of_commercial_shops = number_of_commercial_shops
        self.basement_required = basement_required
        self.corpus_commercial = corpus_commercial
        self.corpus_residential = corpus_residential
        self.bank_guarantee_commercial = bank_guarantee_commercial
        self.bank_guarantee_residential = bank_guarantee_residential
        self.sale_commercial_mun_bua_sqft = sale_commercial_mun_bua_sqft
        self.commercial_area_cost_per_sqft = commercial_area_cost_per_sqft
        self.residential_area_cost_per_sqft = residential_area_cost_per_sqft
        self.podium_parking_cost_per_sqft = podium_parking_cost_per_sqft
        self.basement_cost_per_sqft = basement_cost_per_sqft
        self.cost_acquisition_79a = cost_acquisition_79a
        self.salable_residential_rate = salable_residential_rate
        self.cars_to_sell_rate = cars_to_sell_rate
        self.sale_area_breakup = sale_area_breakup
        self.gf_area = gf_area
        self.gf_rate = gf_rate
        self.f1_area = f1_area
        self.f1_rate = f1_rate
        self.f2_area = f2_area
        self.f2_rate = f2_rate
        self.other_area = other_area
        self.other_rate = other_rate
        self.fsi = fsi
        self.zone_code = zone_code

    def to_orchestrator_payload(self, society_record: Any) -> dict:
        import json

        payload = {
            "society_id": str(society_record.id),
            "society_name": society_record.name,
            "address": society_record.address,
            "num_flats": self.number_of_tenements or 0,
        }

        if self.land_identifier_type and self.land_identifier_value:
            if self.land_identifier_type.upper() == "CTS":
                payload["cts_no"] = self.land_identifier_value
            elif self.land_identifier_type.upper() == "FP":
                payload["fp_no"] = self.land_identifier_value
                payload["use_fp_scheme"] = True

        if self.tps_name:
            payload["tps_name"] = self.tps_name
        if self.plot_area_sqm:
            payload["plot_area_sqm"] = self.plot_area_sqm
        if self.number_of_commercial_shops:
            payload["num_commercial"] = self.number_of_commercial_shops

        manual = {
            "basementRequired": self.basement_required,
            "basement_count": 2 if self.basement_required == "yes" else 0,
            "corpus_commercial": self.corpus_commercial,
            "corpus_residential": self.corpus_residential,
            "bankGuranteeCommercial": self.bank_guarantee_commercial,
            "bankGuranteeResidential": self.bank_guarantee_residential,
            "commercial_bua_sqft": self.sale_commercial_mun_bua_sqft,
            "const_rate_commercial": self.commercial_area_cost_per_sqft,
            "const_rate_residential": self.residential_area_cost_per_sqft,
            "const_rate_podium": self.podium_parking_cost_per_sqft,
            "const_rate_basement": self.basement_cost_per_sqft,
            "costAcquisition79a": self.cost_acquisition_79a,
            "salableResidentialRatePerSqFt": self.salable_residential_rate,
            "carsToSellRatePerCar": self.cars_to_sell_rate,
            "fsi": self.fsi,
            "zone_code": self.zone_code,
        }

        breakup_json = self.sale_area_breakup
        if not breakup_json:
            recon = {}
            if self.gf_area is not None:
                recon["groundFloor"] = {"area": self.gf_area or 0, "rate": self.gf_rate or 0}
            if self.f1_area is not None:
                recon["firstFloor"] = {"area": self.f1_area or 0, "rate": self.f1_rate or 0}
            if recon:
                breakup_json = json.dumps(recon)

        if breakup_json:
            with contextlib.suppress(Exception):
                manual["saleAreaBreakup"] = json.loads(breakup_json)

        payload["manual_inputs"] = {k: v for k, v in manual.items() if v is not None}
        return payload
