#!/usr/bin/env python3
"""
RERA Integration Module
Real API Integration for MahaRERA
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://maharera.mahaonline.gov.in/MahaRERA/api"

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html",
        "Referer": "https://maharera.mahaonline.gov.in",
    }
)


@dataclass
class RERAProject:
    registration_no: str
    project_name: str
    promoter_name: str
    address: str
    total_units: int
    sold_units: int
    available_units: int
    valid_upto: str
    rera_link: str
    status: str


@dataclass
class RERAPromoter:
    registration_no: str
    promoter_name: str
    address: str
    gantt_chart: bool
    bank_details: dict
    status: str


class RERAIntegration:
    """MahaRERA API Integration"""

    def __init__(self):
        self.session = SESSION
        self.cache_dir = Path("data/rera_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_project_by_reg_no(self, reg_no: str) -> dict | None:
        """
        Search project by RERA registration number
        Example: P51800045641
        """
        try:
            # Try the API
            url = f"{BASE_URL}/RegisteredProjects/Search"
            params = {"regNo": reg_no}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                return self._parse_project(data)

            # If API doesn't work, return instructions
            return {
                "error": "API not accessible",
                "alternative": "Check https://maharera.mahaonline.gov.in directly",
                "sample_reg_no": "P51800045641",
                "note": "Government APIs often have rate limits or require authentication",
            }

        except requests.exceptions.Timeout:
            return {"error": "Request timed out"}
        except Exception as e:
            return {"error": str(e)}

    def search_promoter(self, promoter_name: str) -> list[dict]:
        """Search promoter/builder by name"""
        try:
            url = f"{BASE_URL}/Promoter/Search"
            params = {"name": promoter_name}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                return response.json().get("results", [])

            return []

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return []

    def get_project_details(self, project_id: str) -> dict | None:
        """Get detailed project information"""
        try:
            url = f"{BASE_URL}/ProjectDetails/{project_id}"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                return response.json()

            return None

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return None

    def _parse_project(self, data: dict) -> dict:
        """Parse API response"""
        return {
            "registration_no": data.get("registrationNo", ""),
            "project_name": data.get("projectName", ""),
            "promoter_name": data.get("promoterName", ""),
            "address": data.get("address", ""),
            "total_units": data.get("totalUnits", 0),
            "valid_upto": data.get("validUpto", ""),
            "status": data.get("status", ""),
        }

    def check_builder_credibility(self, builder_name: str) -> dict:
        """
        Check builder credibility by searching multiple sources
        """
        results = {
            "builder_name": builder_name,
            "searched_at": datetime.now().isoformat(),
            "rera_registered": False,
            "projects_found": [],
            "warnings": [],
        }

        # Search in RERA
        projects = self.search_promoter(builder_name)

        if projects:
            results["rera_registered"] = True
            results["projects_found"] = projects
            results["message"] = f"Found {len(projects)} projects in RERA"
        else:
            results["warnings"].append("Builder not found in RERA database")
            results["message"] = "Builder may not be RERA registered"

        # Check for red flags
        for project in projects:
            if project.get("status") == "Expired":
                results["warnings"].append(
                    f"Project '{project.get('name')}' has expired registration"
                )

            if not project.get("gantt_chart"):
                results["warnings"].append(f"Project '{project.get('name')}' missing Gantt chart")

        return results

    def verify_registration(self, reg_no: str) -> dict:
        """
        Verify if RERA registration is valid
        """
        result = self.search_project_by_reg_no(reg_no)

        if result and "error" not in result:
            return {
                "valid": True,
                "registration_no": result.get("registration_no"),
                "project_name": result.get("project_name"),
                "promoter": result.get("promoter_name"),
                "valid_upto": result.get("valid_upto"),
            }
        return {
            "valid": False,
            "error": result.get("error", "Registration not found"),
            "check_manually": "https://maharera.mahaonline.gov.in",
        }


def main():
    """Test RERA integration"""
    import argparse

    parser = argparse.ArgumentParser(description="RERA Integration")
    subparsers = parser.add_subparsers(dest="cmd")

    # Search by reg no
    search_parser = subparsers.add_parser("search", help="Search project by RERA no")
    search_parser.add_argument("reg_no", help="RERA registration number")

    # Search promoter
    promoter_parser = subparsers.add_parser("promoter", help="Search promoter by name")
    promoter_parser.add_argument("name", help="Promoter/Builder name")

    # Check credibility
    credible_parser = subparsers.add_parser("credibility", help="Check builder credibility")
    credible_parser.add_argument("name", help="Builder name")

    # Verify
    verify_parser = subparsers.add_parser("verify", help="Verify RERA registration")
    verify_parser.add_argument("reg_no", help="RERA registration number")

    args = parser.parse_args()

    rera = RERAIntegration()

    if args.cmd == "search":
        logger.info(f"Searching for: {args.reg_no}")
        result = rera.search_project_by_reg_no(args.reg_no)
        logger.info(json.dumps(result, indent=2))

    elif args.cmd == "promoter":
        logger.info(f"Searching promoter: {args.name}")
        results = rera.search_promoter(args.name)
        logger.info(f"Found {len(results)} results")
        for r in results:
            logger.info(f"  - {r.get('name')} ({r.get('regNo')})")

    elif args.cmd == "credibility":
        logger.info(f"Checking credibility of: {args.name}")
        result = rera.check_builder_credibility(args.name)
        logger.info(json.dumps(result, indent=2))

    elif args.cmd == "verify":
        logger.info(f"Verifying: {args.reg_no}")
        result = rera.verify_registration(args.reg_no)
        logger.info(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
