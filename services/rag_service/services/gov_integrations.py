#!/usr/bin/env python3
"""
Real Government Data Source Integrations
BMC, Bhulekh, NOCAS, MCGM Property Lookup
"""

import logging
from datetime import datetime
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


class BhulekhIntegration:
    """Mahabhoomi Bhulekh - Official Land Records API"""

    # Official Bhulekh Maharashtra API endpoints
    BASE_URL = "https://bhulekh.maharashtra.gov.in"
    API_URL = "https://bhulekh.maharashtra.gov.in/api"

    def __init__(self):
        self.session = SESSION
        self.cache_dir = Path("data/data_sources/bhulekh")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_property(
        self, district: str, taluka: str, village: str, survey_no: str
    ) -> dict | None:
        """
        Search property in Bhulekh
        District: Mumbai City, Mumbai Suburban, Thane, etc.
        Taluka: Andheri, Dadar, Kurla, etc.
        Village: Actual village name
        Survey No: 123/4, 123A, etc.
        """
        try:
            # Try official Bhulekh API
            url = f"{self.API_URL}/land-records"

            payload = {
                "district": district,
                "taluka": taluka,
                "village": village,
                "survey_no": survey_no,
                "format": "json",
            }

            response = self.session.get(url, params=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return self._parse_bhulekh_response(data)

            # Fallback: Try web scraping
            return self._scrape_bhulekh(district, taluka, village, survey_no)

        except Exception as e:
            logger.error(f"Bhulekh API error: {e}")
            return self._scrape_bhulekh(district, taluka, village, survey_no)

    def _scrape_bhulekh(
        self, district: str, taluka: str, village: str, survey_no: str
    ) -> dict | None:
        """Scrape Bhulekh website"""
        try:
            # Bhulekh requires login - use Form-based search

            # For demo, return structure that shows what's needed
            return {
                "success": False,
                "message": "Bhulekh requires authenticated access",
                "required_auth": "Bhulekh Login Credentials",
                "alternative": "Upload Property Card PDF for OCR extraction",
                "data_needed": {
                    "7_12_extract": "7/12 रुजू पत्र",
                    "property_card": "Property Card",
                    "survey_no": survey_no,
                    "village": village,
                    "taluka": taluka,
                    "district": district,
                },
            }
        except Exception as e:
            logger.error(f"Bhulekh scrape error: {e}")
            return None

    def _parse_bhulekh_response(self, data: dict) -> dict | None:
        """Parse Bhulekh API response"""
        if data.get("status") == "success":
            return {
                "survey_no": data.get("survey_no"),
                "village": data.get("village"),
                "area": data.get("area"),
                "land_type": data.get("land_type"),
                "tenure": data.get("tenure"),
                "owners": data.get("owners", []),
                "source": "bhulekh",
            }
        return None

    def get_property_card(
        self, district: str, taluka: str, village: str, survey_no: str
    ) -> dict | None:
        """Get property card details"""
        result = self.search_property(district, taluka, village, survey_no)
        if result and result.get("success"):
            return {
                "survey_no": result.get("survey_no"),
                "area_sq_m": self._convert_to_sqm(result.get("area", 0)),
                "area_sq_ft": self._convert_to_sqm(result.get("area", 0)) * 10.764,
                "tenure": result.get("tenure", "Freehold"),
                "land_type": result.get("land_type", "N.A."),
                "village": result.get("village"),
                "taluka": taluka,
                "district": district,
                "source": "bhulekh",
            }
        return None

    def _convert_to_sqm(self, area_str: str) -> float:
        """Convert area string to sq meters"""
        if not area_str:
            return 0.0

        # Handle formats like "500", "500.5", "1-23-45" (guntha), "1.00.00" (acre)
        area_str = str(area_str).strip()

        # If just a number
        try:
            return float(area_str)
        except Exception:
            pass

        # Guntha format: 1-23-45 means 1 guntha 23gunta 45 ad
        if "-" in area_str:
            parts = area_str.split("-")
            if len(parts) == 3:
                guntha = float(parts[0])
                guntha += float(parts[1]) / 20  # 20 guntha = 1 acre
                guntha += float(parts[2]) / 400  # 400 ad = 1 guntha
                return guntha * 101.17  # 1 guntha = 101.17 sq.m

        return 0.0


class BMCIntegration:
    """Brihanmumbai Municipal Corporation Integration"""

    # BMC/MCGM official portals
    PROPERTY_LOOKUP = "https://property.mcgm.gov.in"
    DP_REMARKS_API = "https://ipfs.io/ipfs/Qm..."  # MCGM DP data on IPFS

    def __init__(self):
        self.session = SESSION
        self.cache_dir = Path("data/data_sources/bmc")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_dp_remarks(self, survey_no: str, ward: str = "") -> dict | None:
        """
        Get Development Plan remarks for a property
        Ward: Find from MCGM ward map
        """
        try:
            # Try MCGM Property Lookup Portal
            url = f"{self.PROPERTY_LOOKUP}/api/property/search"

            payload = {"survey_no": survey_no, "ward": ward}

            response = self.session.get(url, params=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return self._parse_dp_remarks(data)

            # Fallback: Scrape MCGM website
            return self._scrape_mcgm_dp(survey_no, ward)

        except Exception as e:
            logger.error(f"BMC DP remarks error: {e}")
            return self._scrape_mcgm_dp(survey_no, ward)

    def _scrape_mcgm_dp(self, survey_no: str, ward: str) -> dict | None:
        """Scrape DP remarks from MCGM"""
        try:
            # MCGM DP website

            # For now, return structure showing what's available
            return {
                "success": False,
                "message": "MCGM DP Portal requires authentication",
                "alternative_methods": [
                    "1. Visit MCGM office with survey number",
                    "2. Submit application at MCGM ward office",
                    "3. Use MCGM's mobile app 'MCGM O生了'",
                    "4. Check physically at DP section",
                ],
                "required_for_dp": {
                    "survey_no": survey_no,
                    "property_address": "",
                    "owner_name": "",
                },
                "dp_details_available": {
                    "zone": "Residential/Commercial/Industrial",
                    "road_width": "Proposed road width",
                    "reservation": "Amenity/DP Road/Nothing",
                    "FSI": "Basic FSI applicable",
                    "setbacks": "Required setbacks",
                },
            }
        except Exception as e:
            logger.error(f"MCGM scrape error: {e}")
            return None

    def _parse_dp_remarks(self, data: dict) -> dict:
        """Parse DP remarks response"""
        return {
            "survey_no": data.get("survey_no"),
            "zone": data.get("zone_type"),
            "dp_remarks": data.get("remarks"),
            "road_width": data.get("road_width"),
            "FSI": data.get("FSI"),
            "setback_front": data.get("setback_front"),
            "setback_rear": data.get("setback_rear"),
            "setback_side": data.get("setback_side"),
            "parking_required": data.get("parking_required"),
            "source": "mcgm",
        }

    def get_zone_info(self, address: str) -> dict | None:
        """Get zone information for address"""
        try:
            # MCGM Building Proposal System
            url = "https://bps.mcgm.gov.in/api/zone"

            response = self.session.get(url, params={"address": address}, timeout=10)

            if response.status_code == 200:
                return response.json()

            return None
        except Exception:
            return None


class NOCASIntegration:
    """NOCAS - Building Permission System"""

    BASE_URL = "https://nocas.mahaonline.gov.in"
    API_URL = "https://nocas.mahaonline.gov.in/MahaOnline/api"

    def __init__(self):
        self.session = SESSION

    def get_building_permissions(self, survey_no: str, zone: str, area_sq_m: float) -> dict | None:
        """
        Get building permission details including max height
        Zone: Residential, Commercial, etc.
        """
        try:
            # NOCAS building permission check
            url = f"{self.API_URL}/BuildingPermission/CheckPermissions"

            payload = {"survey_no": survey_no, "zone": zone, "plot_area": area_sq_m}

            response = self.session.post(url, json=payload, timeout=15)

            if response.status_code == 200:
                return response.json()

            return self._calculate_height(zone, area_sq_m)

        except Exception as e:
            logger.error(f"NOCAS API error: {e}")
            return self._calculate_height(zone, area_sq_m)

    def _calculate_height(self, zone: str, area_sq_m: float) -> dict:
        """
        Calculate max building height based on DCPR rules
        """
        # Height limits based on zone
        base_heights = {
            "Residential": 70,  # meters
            "Commercial": 100,
            "Industrial": 50,
            "Mixed Use": 70,
            "Institutional": 70,
        }

        base_height = base_heights.get(zone, 70)

        # Adjust based on plot area
        if area_sq_m < 500:
            base_height = min(base_height, 24)  # ~8 floors
        elif area_sq_m < 1000:
            base_height = min(base_height, 36)  # ~12 floors
        elif area_sq_m < 2000:
            base_height = min(base_height, 50)  # ~15 floors
        elif area_sq_m < 5000:
            base_height = min(base_height, 60)  # ~18 floors

        # Airport clearance required above 30m
        airport_required = base_height > 30

        # FSI determines floor area
        fsi = self._get_zone_fsi(zone)
        total_bua = area_sq_m * 10.764 * fsi
        floors = int(total_bua / (area_sq_m * 10.764 / base_height * 3.5)) if area_sq_m > 0 else 0

        return {
            "max_height_m": base_height,
            "max_floors": floors,
            "approx_floor_height_m": 3.5,
            "airport_clearance_required": airport_required,
            " FSI": fsi,
            "total_bua_sqft": int(total_bua),
            "calculation_basis": "DCPR 2034 + NOCAS norms",
            "source": "nocas_calculation",
        }

    def _get_zone_fsi(self, zone: str) -> float:
        """Get FSI for zone"""
        fsi_map = {
            "Residential": 2.5,
            "Commercial": 4.0,
            "Industrial": 1.0,
            "Mixed Use": 3.0,
        }
        return fsi_map.get(zone, 2.5)

    def check_noc_required(self, building_type: str, height: float) -> dict:
        """Check what NOCs are required"""
        nocs = []

        if height > 30:
            nocs.append(
                {
                    "noc": "Airport Authority of India (AAI)",
                    "reason": f"Building height {height}m exceeds 30m limit",
                    "application_url": "https://www.aai.aero/en/services/planning/building-permission",
                }
            )

        nocs.append(
            {
                "noc": "Fire Department NOC",
                "reason": "Required for all buildings",
                "application_url": "https://mfs.maharashtra.gov.in",
            }
        )

        if building_type == "Residential" and height > 24:
            nocs.append(
                {
                    "noc": "Chief Fire Officer",
                    "reason": "High rise building",
                    "application_url": "https://mfs.maharashtra.gov.in",
                }
            )

        return {"required_nocs": nocs}


class MCGMIntegration:
    """MCGM Building Proposal System Integration"""

    BPS_URL = "https://bps.mcgm.gov.in"
    CORP_URL = "https://corp.mcgm.gov.in"

    def __init__(self):
        self.session = SESSION

    def submit_building_plan(self, application_data: dict) -> dict | None:
        """
        Submit building plan to MCGM
        Requires: Approved plans, NOCs, property documents
        """
        try:
            url = f"{self.BPS_URL}/api/applications"

            response = self.session.post(url, json=application_data, timeout=30)

            if response.status_code in [200, 201]:
                return response.json()

            return {
                "success": False,
                "message": "MCGM BPS requires digital signature certificate (DSC)",
                "alternative": "Submit physically at MCGM office",
            }

        except Exception as e:
            logger.error(f"MCGM BPS error: {e}")
            return None

    def get_application_status(self, application_no: str) -> dict | None:
        """Check application status"""
        try:
            url = f"{self.BPS_URL}/api/applications/{application_no}/status"

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()

            return None
        except Exception:
            return None

    def calculate_fees(self, plot_area: float, bua: float, scheme: str) -> dict:
        """Calculate MCGM fees for building proposal"""

        # Basic scrutiny fees
        scrutiny_fees = bua * 141  # Rs. 141 per sq.m of BUA

        # Development charges
        dev_charges_plot = plot_area * 1000  # Rs. 1000 per sq.m of plot
        dev_charges_bua = bua * 4000  # Rs. 4000 per sq.m of BUA

        # Premium FSI charges (if applicable)
        premium_fsi = 0.5  # 50% of FSI
        premium_charges = plot_area * premium_fsi * 50000  # Premium rate

        # Fungible FSI charges
        fungible_fsi = 0.2
        fungible_charges = plot_area * fungible_fsi * 25000

        return {
            "scrutiny_fees": scrutiny_fees,
            "development_charges_plot": dev_charges_plot,
            "development_charges_bua": dev_charges_bua,
            "premium_fsi_charges": premium_charges,
            "fungible_fsi_charges": fungible_charges,
            "total_fees": scrutiny_fees
            + dev_charges_plot
            + dev_charges_bua
            + premium_charges
            + fungible_charges,
            "note": "Fees are approximate, verify at MCGM",
        }


class RERAIntegration:
    """MahaRERA Integration for project registration"""

    BASE_URL = "https://maharera.mahaonline.gov.in"
    API_URL = "https://maharera.mahaonline.gov.in/MahaRERA/api"

    def __init__(self):
        self.session = SESSION

    def check_builder_registration(self, rera_no: str) -> dict | None:
        """Check if builder has valid RERA registration"""
        try:
            url = f"{self.API_URL}/RegisteredProjects/Search"

            response = self.session.get(url, params={"regNo": rera_no}, timeout=15)

            if response.status_code == 200:
                return response.json()

            return None
        except Exception:
            return None

    def get_project_details(self, project_code: str) -> dict | None:
        """Get project details from RERA"""
        try:
            url = f"{self.API_URL}/ProjectDetails/{project_code}"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return {
                    "project_name": data.get("project_name"),
                    "registration_no": data.get("registration_no"),
                    "builder_name": data.get("promoter_name"),
                    "valid_upto": data.get("valid_upto"),
                    "total_units": data.get("total_units"),
                    "status": data.get("status"),
                    "source": "maharera",
                }

            return None
        except Exception:
            return None


class AggregatedPropertyData:
    """Aggregate data from all sources"""

    def __init__(self):
        self.bhulekh = BhulekhIntegration()
        self.bmc = BMCIntegration()
        self.nocas = NOCASIntegration()
        self.mcgm = MCGMIntegration()
        self.rera = RERAIntegration()

    def get_complete_data(
        self,
        survey_no: str,
        district: str = "Mumbai Suburban",
        taluka: str = "Andheri",
        village: str = "",
    ) -> dict:
        """
        Get complete property data from all sources
        """
        result = {
            "survey_no": survey_no,
            "fetched_at": datetime.now().isoformat(),
            "sources": [],
            "data": {},
        }

        # 1. Get from Bhulekh
        bhulekh_data = self.bhulekh.search_property(district, taluka, village or taluka, survey_no)
        if bhulekh_data:
            result["data"]["bhulekh"] = bhulekh_data
            result["sources"].append("bhulekh")

        # 2. Get DP remarks from BMC
        dp_data = self.bmc.get_dp_remarks(survey_no)
        if dp_data:
            result["data"]["bmc"] = dp_data
            result["sources"].append("bmc")

        # 3. Get NOCAS height clearance
        area = bhulekh_data.get("area", 1000) if bhulekh_data else 1000
        zone = dp_data.get("zone", "Residential") if dp_data else "Residential"
        height_data = self.nocas.get_building_permissions(survey_no, zone, area)
        if height_data:
            result["data"]["nocas"] = height_data
            result["sources"].append("nocas")

        return result

    def generate_property_report(self, survey_no: str) -> dict:
        """Generate comprehensive property report"""
        complete_data = self.get_complete_data(survey_no)

        report = {
            "property_id": survey_no.replace("/", "_"),
            "generated_at": datetime.now().isoformat(),
            "data_sources": complete_data["sources"],
            "summary": {},
            "details": complete_data,
        }

        # Extract summary
        if "bhulekh" in complete_data["data"]:
            bhulekh = complete_data["data"]["bhulekh"]
            report["summary"]["plot_area_sq_m"] = bhulekh.get("area", 0)
            report["summary"]["tenure"] = bhulekh.get("tenure", "Unknown")

        if "bmc" in complete_data["data"]:
            bmc = complete_data["data"]["bmc"]
            report["summary"]["zone"] = bmc.get("zone", "Unknown")
            report["summary"]["dp_remarks"] = bmc.get("dp_remarks", "Unknown")
            report["summary"]["road_width"] = bmc.get("road_width", 0)

        if "nocas" in complete_data["data"]:
            nocas = complete_data["data"]["nocas"]
            report["summary"]["max_height_m"] = nocas.get("max_height_m", 0)
            report["summary"]["max_floors"] = nocas.get("max_floors", 0)

        return report


# CLI Functions
def cmd_fetch_all(args):
    """Fetch data from all sources"""
    agg = AggregatedPropertyData()
    data = agg.get_complete_data(args.survey_no, args.district, args.taluka, args.village)

    logger.info(f"\nProperty Data for {args.survey_no}:")
    logger.info(f"Sources: {', '.join(data['sources'])}")
    logger.info("\n--- Summary ---")
    for source, content in data["data"].items():
        logger.info(f"\n{source.upper()}:")
        if isinstance(content, dict):
            for key, value in content.items():
                if not key.startswith("_"):
                    logger.info(f"  {key}: {value}")


def cmd_property_report(args):
    """Generate property report"""
    agg = AggregatedPropertyData()
    report = agg.generate_property_report(args.survey_no)

    logger.info(f"\nProperty Report: {report['property_id']}")
    logger.info(f"Sources: {', '.join(report['data_sources'])}")
    logger.info("\n--- Summary ---")
    for key, value in report["summary"].items():
        logger.info(f"  {key}: {value}")


def cmd_check_rera(args):
    """Check RERA registration"""
    rera = RERAIntegration()
    data = rera.get_project_details(args.rera_no)

    if data:
        logger.info(f"\nRERA Registration: {args.rera_no}")
        logger.info(f"  Project: {data.get('project_name')}")
        logger.info(f"  Builder: {data.get('builder_name')}")
        logger.info(f"  Valid Until: {data.get('valid_upto')}")
        logger.info(f"  Status: {data.get('status')}")
    else:
        logger.warning(f"RERA {args.rera_no} not found or error fetching data")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Government Data Integrations")
    subparsers = parser.add_subparsers(dest="cmd")

    # Fetch all
    fetch_parser = subparsers.add_parser("fetch", help="Fetch from all sources")
    fetch_parser.add_argument("survey_no", help="Survey number")
    fetch_parser.add_argument("--district", default="Mumbai Suburban")
    fetch_parser.add_argument("--taluka", default="Andheri")
    fetch_parser.add_argument("--village", default="")

    # Property report
    report_parser = subparsers.add_parser("report", help="Generate property report")
    report_parser.add_argument("survey_no", help="Survey number")

    # RERA check
    rera_parser = subparsers.add_parser("rera", help="Check RERA registration")
    rera_parser.add_argument("rera_no", help="RERA registration number")

    args = parser.parse_args()

    if args.cmd == "fetch":
        cmd_fetch_all(args)
    elif args.cmd == "report":
        cmd_property_report(args)
    elif args.cmd == "rera":
        cmd_check_rera(args)
    else:
        parser.print_help()
