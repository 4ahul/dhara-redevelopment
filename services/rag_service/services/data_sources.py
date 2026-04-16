#!/usr/bin/env python3
"""
Government Data Sources Integration
Fetches data from: Mahabhoomi Bhulekh, BMC, NOCAS, MCGM
"""

import json
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_SOURCES_DIR = DATA_DIR / "data_sources"
CACHE_DIR = DATA_SOURCES_DIR / "cache"
COMPLIANCE_DIR = DATA_SOURCES_DIR / "compliance"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
COMPLIANCE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PropertyDetails:
    survey_no: str = ""
    cts_no: str = ""
    plot_area_sq_m: float = 0.0
    plot_area_sq_ft: float = 0.0
    road_width_m: float = 0.0
    zone_type: str = ""
    max_height_m: float = 0.0
    max_fsi: float = 0.0
    dp_remarks: str = ""
    village: str = ""
    taluka: str = ""
    district: str = ""
    pincode: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    property_type: str = ""
    tenure: str = ""
    existing_structure: Dict = field(default_factory=dict)
    setback_details: Dict = field(default_factory=dict)
    amenity_details: Dict = field(default_factory=dict)
    data_source: str = ""
    last_updated: datetime = None


@dataclass
class ComplianceRegulation:
    regulation_id: str = ""
    title: str = ""
    description: str = ""
    effective_date: datetime = None
    source: str = ""
    category: str = ""  # dcpr, fire, environment, rera, etc.
    applicability: List[str] = field(default_factory=list)  # schemes this applies to
    url: str = ""
    file_path: str = ""


class DataSource(ABC):
    """Base class for data sources"""

    def __init__(self, name: str, cache_ttl_hours: int = 24):
        self.name = name
        self.cache_ttl = cache_ttl_hours * 3600
        self.cache_dir = CACHE_DIR / name.replace(" ", "_").lower()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache(self, key: str) -> Optional[Dict]:
        """Get cached data if valid"""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                age = time.time() - mtime
                if age < self.cache_ttl:
                    return json.loads(cache_file.read_text())
            except:
                pass
        return None

    def _set_cache(self, key: str, data: Dict):
        """Cache data"""
        try:
            cache_file = self.cache_dir / f"{key}.json"
            cache_file.write_text(json.dumps(data, indent=2, default=str))
        except:
            pass

    @abstractmethod
    def fetch(self, query: str) -> Optional[Dict]:
        """Fetch data from source"""
        pass


class BhulekhMahabhoomi(DataSource):
    """Mahabhoomi Bhulekh - PR Card data"""

    BASE_URL = "https://bhulekh.maharashtra.gov.in"

    def __init__(self):
        super().__init__("bhulekh", cache_ttl_hours=168)  # 1 week cache

    def fetch(self, survey_no: str, village: str = "") -> Optional[PropertyDetails]:
        """Fetch property details from Bhulekh"""

        # Check cache first
        cache_key = f"{survey_no}_{village}".replace("/", "_")
        cached = self._get_cache(cache_key)
        if cached:
            logger.info(f"Cache hit for {survey_no}")
            return self._parse_property(cached)

        try:
            # In production, this would call the actual API
            # For now, we'll create a mock response structure

            # Try scraping if API not available
            data = self._scrape_bhulekh(survey_no, village)

            if data:
                self._set_cache(cache_key, data)
                return self._parse_property(data)

            return None

        except Exception as e:
            logger.error(f"Bhulekh fetch error: {e}")
            return None

    def _scrape_bhulekh(self, survey_no: str, village: str) -> Optional[Dict]:
        """Scrape Bhulekh website (DEPRECATED - use pr_card_scraper microservice)"""
        logger.warning(
            "Bhulekh scraping in RAG service is deprecated. "
            "Use the dedicated 'pr_card_scraper' microservice for real land records."
        )
        return None

    def _parse_property(self, data: Dict) -> PropertyDetails:
        """Parse Bhulekh data to PropertyDetails"""
        if not data:
            return PropertyDetails()
        return PropertyDetails(
            survey_no=data.get("survey_no", ""),
            plot_area_sq_m=float(data.get("plot_area", 0)),
            plot_area_sq_ft=float(data.get("plot_area", 0)) * 10.764,
            tenure=data.get("tenure", ""),
            village=data.get("village", ""),
            data_source="bhulekh",
            last_updated=datetime.now(),
        )


class BMCDataSource(DataSource):
    """Brihanmumbai Municipal Corporation - DP Remarks, Property Lookup (DEPRECATED - use dedicated services)"""

    def __init__(self):
        super().__init__("bmc", cache_ttl_hours=24)

    def fetch(self, query: str = "") -> Optional[Dict]:
        """Fetch BMC data - generic fetch not implemented, use specific methods"""
        return None

    def fetch_dp_remarks(self, survey_no: str) -> Optional[Dict]:
        """Fetch DP remarks from BMC (DEPRECATED - use dp_report_service)"""

        cache_key = f"dp_{survey_no}".replace("/", "_")
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        logger.warning(
            "BMC DP remarks fetch in RAG service is deprecated. "
            "Use the dedicated 'dp_report_service' for real-time MCGM/BMC data."
        )
        return None

    def fetch_property_lookup(self, address: str) -> Optional[Dict]:
        """Fetch property details from MCGM Property Lookup"""

        try:
            # MCGM Property Lookup: https://property.mcgm.gov.in/

            return {
                "address": address,
                "ward": "",
                "zone": "Residential",
                "building_use": "Residential",
                "source": "mcgm_property_lookup",
            }
        except Exception as e:
            logger.error(f"MCGM Property Lookup error: {e}")
            return None


class NOCASDataSource(DataSource):
    """NOCAS Website - Building height and NOC related data"""

    BASE_URL = "https://nocas.mahaonline.gov.in"

    def __init__(self):
        super().__init__("nocas", cache_ttl_hours=24)

    def fetch(self, query: str = "") -> Optional[Dict]:
        """Fetch NOCAS data - generic fetch not implemented, use specific methods"""
        return None

    def fetch_building_height(
        self, survey_no: str, zone: str, area_sq_m: float
    ) -> Optional[Dict]:
        """Fetch max building height allowed (DEPRECATED - use height_service)"""

        logger.warning(
            "NOCAS height fetch in RAG service is deprecated. "
            "Use the dedicated 'height_service' for real-time NOCAS data."
        )
        return None

    def _calculate_max_height(self, zone: str, area_sq_m: float) -> Dict:
        """DEPRECATED - Use height_service instead."""
        return {}


class ComplianceDataSource(DataSource):
    """Government compliance regulations - WhatsApp, official sources"""

    def __init__(self):
        super().__init__("compliance", cache_ttl_hours=1)  # Short cache
        self.compliance_file = COMPLIANCE_DIR / "regulations.json"
        self._init_compliance_db()

    def fetch(self, query: str = "") -> Optional[Dict]:
        """Fetch compliance data - generic fetch not implemented, use specific methods"""
        return None

    def _init_compliance_db(self):
        """Initialize compliance database"""
        if not self.compliance_file.exists():
            default_regs = [
                {
                    "regulation_id": "DCPR_2034",
                    "title": "Development Control Promotion Rules 2034",
                    "description": "Mumbai DCPR regulations for FSI, setbacks, parking",
                    "effective_date": "2024-01-01",
                    "source": "Official Gazette",
                    "category": "dcpr",
                    "applicability": ["33(7B)", "33(20B)", "33(11)", "30(A)"],
                },
                {
                    "regulation_id": "RERA_2016",
                    "title": "Real Estate Regulation Act 2016",
                    "description": "RERA carpet area, registration, escrow",
                    "effective_date": "2017-05-01",
                    "source": "RERA Mumbai",
                    "category": "rera",
                    "applicability": ["all"],
                },
                {
                    "regulation_id": "MahaRERA_ORD_2024",
                    "title": "MahaRERA Circular on Deemed Conveyance",
                    "description": "Process for deemed conveyance under RERA",
                    "effective_date": "2024-03-01",
                    "source": "MahaRERA",
                    "category": "rera",
                    "applicability": ["deemed_conveyance"],
                },
            ]
            self.compliance_file.write_text(json.dumps(default_regs, indent=2))

    def fetch_compliances(self, scheme: str = "") -> List[ComplianceRegulation]:
        """Fetch applicable compliances"""

        try:
            data = json.loads(self.compliance_file.read_text())
            regs = []
            for r in data:
                if (
                    not scheme
                    or scheme in r.get("applicability", [])
                    or "all" in r.get("applicability", [])
                ):
                    regs.append(
                        ComplianceRegulation(
                            regulation_id=r["regulation_id"],
                            title=r["title"],
                            description=r["description"],
                            effective_date=datetime.fromisoformat(r["effective_date"])
                            if r.get("effective_date")
                            else None,
                            source=r.get("source", ""),
                            category=r.get("category", ""),
                            applicability=r.get("applicability", []),
                        )
                    )
            return regs
        except:
            return []

    def add_compliance(self, regulation: Dict):
        """Add new compliance from WhatsApp or official source"""
        try:
            data = json.loads(self.compliance_file.read_text())
            data.append(regulation)
            self.compliance_file.write_text(json.dumps(data, indent=2))
            return True
        except:
            return False

    def parse_whatsapp_message(self, message: str) -> Optional[Dict]:
        """Parse WhatsApp message for compliance updates"""

        # Pattern to detect compliance updates
        patterns = [
            r"(?i)(new|amended|updated)\s+(regulation|rule|circular|order|notification)\s*[:\-]?\s*(.+)",
            r"(?i)(effective|from)\s*(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})\s*[:\-]?\s*(.+)",
            r"(?i)(DCPR|DCR|RERA|MahaRERA)\s*[:\-]?\s*(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return {
                    "regulation_id": f"IMPORTED_{datetime.now().strftime('%Y%m%d%H%M')}",
                    "title": match.group(3)
                    if len(match.groups()) > 2
                    else message[:100],
                    "description": message,
                    "effective_date": datetime.now().isoformat(),
                    "source": "WhatsApp Import",
                    "category": "imported",
                    "applicability": ["all"],
                }

        return None


class PropertyDataAggregator:
    """Aggregate data from all sources"""

    def __init__(self):
        self.bhulekh = BhulekhMahabhoomi()
        self.bmc = BMCDataSource()
        self.nocas = NOCASDataSource()
        self.compliance = ComplianceDataSource()

    def get_complete_property_data(
        self, cts_no: str, village: str = ""
    ) -> PropertyDetails:
        """Get complete property data from all sources"""

        # Fetch from Bhulekh
        bhulekh_data = self.bhulekh.fetch(cts_no, village)

        # Fetch DP remarks from BMC
        dp_data = self.bmc.fetch_dp_remarks(cts_no)

        # Fetch from NOCAS
        area = bhulekh_data.plot_area_sq_m if bhulekh_data else 1000
        zone = dp_data.get("zone", "Residential") if dp_data else "Residential"
        nocas_data = self.nocas.fetch_building_height(cts_no, zone, area)

        # Aggregate
        property_details = PropertyDetails(
            survey_no=cts_no,
            cts_no=cts_no,
            village=village,
            data_source="aggregated",
            last_updated=datetime.now(),
        )

        if bhulekh_data:
            property_details.plot_area_sq_m = bhulekh_data.plot_area_sq_m
            property_details.plot_area_sq_ft = bhulekh_data.plot_area_sq_ft
            property_details.tenure = bhulekh_data.tenure

        if dp_data:
            property_details.dp_remarks = dp_data.get("dp_remarks", "")
            property_details.road_width_m = dp_data.get("road_width_proposed", 9)
            property_details.zone_type = dp_data.get("zone", "Residential")

        if nocas_data:
            property_details.max_height_m = nocas_data.get("max_height_m", 70)

        return property_details

    def get_applicable_compliances(
        self, scheme: str = ""
    ) -> List[ComplianceRegulation]:
        """Get all applicable compliances"""
        return self.compliance.fetch_compliances(scheme)


class FeasibilityReportGenerator:
    """Generate automated feasibility reports with RAG integration"""

    def __init__(self):
        self.aggregator = PropertyDataAggregator()
        self._rag_agent = None

    @property
    def rag_agent(self):
        """Lazy load RAG agent"""
        if self._rag_agent is None:
            from rag import RAGAgent

            self._rag_agent = RAGAgent(use_milvus=True)
        return self._rag_agent

    def _query_rag_for_clauses(self, property_data) -> Dict:
        """Query RAG system for best DCPR clauses"""
        try:
            area = property_data.plot_area_sq_m
            road = property_data.road_width_m
            zone = property_data.zone_type

            queries = [
                f"FSI regulations {zone} zone {road}m road width",
                "DCPR 33(7B) 33(20B) residential redevelopment",
                f"open space setbacks marginal distances {zone}",
                f"building permission {zone} zone DCPR requirements",
            ]

            rag_results = []
            for query in queries:
                results = self.rag_agent.vectorstore.search(query, k=2)
                rag_results.extend(
                    [
                        {"query": query, "score": r[0], "text": r[1][:500]}
                        for r in results
                    ]
                )

            applicable_clauses = []
            for result in rag_results[:8]:
                clause_summary = self._extract_clause_info(result["text"])
                if clause_summary:
                    applicable_clauses.append(clause_summary)

            return {
                "applicable_clauses": applicable_clauses,
                "dcpr_analysis": rag_results[:4] if rag_results else [],
                "recommended_regulations": self._get_regulation_summary(
                    applicable_clauses
                ),
            }
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return {
                "applicable_clauses": [],
                "dcpr_analysis": [],
                "recommended_regulations": {},
            }

    def _extract_clause_info(self, text: str) -> Optional[Dict]:
        """Extract clause information from text"""
        clause_match = re.search(r"Clause\s*(\d+(?:\(\w+\))?)", text, re.IGNORECASE)
        table_match = re.search(r"Table\s*No\.?\s*(\d+[a-zA-Z]?)", text, re.IGNORECASE)

        if clause_match or table_match:
            return {
                "clause": clause_match.group(1) if clause_match else "N/A",
                "table": table_match.group(1) if table_match else "N/A",
                "summary": text[:300],
            }
        return None

    def _get_regulation_summary(self, clauses: List[Dict]) -> Dict:
        """Get summary of recommended regulations"""
        return {
            "clause_33_7B": any("33(7)" in str(c) for c in clauses),
            "clause_33_20B": any("33(20)" in str(c) for c in clauses),
            "has_fsi_table": any(
                c.get("table") and c["table"] != "N/A" for c in clauses
            ),
            "total_clauses": len(clauses),
        }

    def generate_from_cts(self, cts_no: str, village: str = "") -> Dict:
        """Generate feasibility report from CTS number"""

        # Step 1: Get property data from all sources
        property_data = self.aggregator.get_complete_property_data(cts_no, village)

        # Step 2: Query RAG for applicable clauses
        rag_analysis = self._query_rag_for_clauses(property_data)

        # Step 3: Get applicable compliances
        compliances = self.aggregator.get_applicable_compliances()

        # Step 4: Calculate FSI for all schemes
        from property_card_workflow import DCPRCalculator

        calc = DCPRCalculator()
        schemes = ["33(7B)", "33(20B)", "33(11)", "30(A)"]
        scheme_configs = {}

        for scheme in schemes:
            try:
                config = calc.calculate_scheme(
                    scheme,
                    property_data.plot_area_sq_m,
                    property_data.road_width_m,
                    property_data.zone_type,
                    affordable_housing_pct=70,
                )
                scheme_configs[scheme] = {
                    "basic_fsi": config.basic_fsi,
                    "incentive_fsi": config.incentive_fsi,
                    "max_permissible_fsi": config.max_permissible_fsi,
                    "premium_fsi": config.premium_fsi,
                    "fungible_fsi": config.fungible_fsi,
                    "total_fsi": config.basic_fsi + config.incentive_fsi,
                    "max_bua_sqft": int(
                        property_data.plot_area_sq_ft
                        * (config.basic_fsi + config.incentive_fsi)
                    ),
                }
            except:
                pass

        # Step 5: Get NOCAS height
        nocas = NOCASDataSource()
        height_data = nocas.fetch_building_height(
            cts_no, property_data.zone_type, property_data.plot_area_sq_m
        )

        # Step 6: Find best scheme
        best_scheme_name, best_scheme = self._find_best_scheme(scheme_configs)

        # Step 7: Generate report with RAG insights
        report = {
            "report_id": f"FEAS_{cts_no.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now().isoformat(),
            "cts_no": cts_no,
            "property_details": asdict(property_data),
            "fsi_analysis": scheme_configs,
            "best_scheme": best_scheme_name,
            "best_scheme_details": best_scheme,
            "height_analysis": height_data,
            "applicable_compliances": [asdict(c) for c in compliances],
            "dcpr_clauses": rag_analysis.get("applicable_clauses", []),
            "recommended_regulations": rag_analysis.get("recommended_regulations", {}),
            "recommendation": self._generate_recommendation(
                scheme_configs, best_scheme_name, rag_analysis
            ),
            "next_steps": self._generate_next_steps(best_scheme_name, rag_analysis),
        }

        return report

    def _find_best_scheme(self, schemes: Dict) -> tuple:
        """Find best scheme based on FSI and development potential"""
        if not schemes:
            return "None", {}

        best = max(schemes.items(), key=lambda x: x[1].get("total_fsi", 0))
        return best[0], best[1]

    def _generate_next_steps(self, best_scheme: str, rag_analysis: Dict) -> List[str]:
        """Generate next steps based on best scheme and RAG analysis"""
        steps = [
            f"1. Apply for development under DCPR {best_scheme}",
            "2. Obtain society resolution (70% consent)",
            "3. Engage architect for building plans",
        ]

        if rag_analysis.get("recommended_regulations", {}).get("has_fsi_table"):
            steps.append("4. Refer to DCPR Table 12 for permissible FSI")

        steps.extend(
            [
                "5. Submit to MCGM for provisional approval",
                "6. Obtain NOC from Fire Department",
                "7. Commence construction after IOD",
            ]
        )

        return steps

    def _generate_recommendation(
        self, schemes: Dict, best_scheme: str = "", rag_analysis: Dict = None
    ) -> str:
        """Generate recommendation based on schemes and RAG analysis"""
        if not schemes:
            return "Unable to determine recommendation. Please verify property details."

        if not best_scheme:
            best = max(schemes.items(), key=lambda x: x[1].get("total_fsi", 0))
            best_scheme_name = best[0]
            best_fsi = best[1].get("total_fsi", 0)
        else:
            best_scheme_name = best_scheme
            best_fsi = schemes.get(best_scheme, {}).get("total_fsi", 0)

        rag_info = ""
        if rag_analysis and rag_analysis.get("applicable_clauses"):
            clauses = rag_analysis["applicable_clauses"]
            if clauses:
                rag_info = f" Key clauses: {', '.join([c.get('clause', 'N/A') for c in clauses[:3] if c.get('clause')])}"

        if best_fsi >= 2.5:
            return f"HIGH FSI potential ({best_fsi}) with scheme {best_scheme_name}. Development financially viable.{rag_info}"
        elif best_fsi >= 1.5:
            return f"MODERATE FSI ({best_fsi}) with scheme {best_scheme_name}. Standard redevelopment recommended.{rag_info}"
        else:
            return f"LOW FSI ({best_fsi}). Limited development potential. Consider plot amalgamation."


class TenderGenerator:
    """Generate tender documents for MCGM"""

    def __init__(self):
        self.template_dir = DATA_DIR / "templates"
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def generate_tender(
        self, feasibility_report: Dict, tender_type: str = "e_tender"
    ) -> Dict:
        """Generate tender document from feasibility report"""

        property_data = feasibility_report["property_details"]
        fsi = feasibility_report["fsi_analysis"]

        # Select best scheme
        best_scheme = max(fsi.items(), key=lambda x: x[1].get("total_fsi", 0))

        tender = {
            "tender_id": f"TENDER_{datetime.now().strftime('%Y%m%d%H%M')}",
            "type": tender_type,
            "generated_at": datetime.now().isoformat(),
            "property": {
                "cts_no": property_data.get("survey_no", ""),
                "plot_area_sq_m": property_data.get("plot_area_sq_m", 0),
                "plot_area_sq_ft": property_data.get("plot_area_sq_ft", 0),
                "zone": property_data.get("zone_type", ""),
                "road_width": property_data.get("road_width_m", 0),
            },
            "scheme": {
                "name": best_scheme[0],
                "basic_fsi": best_scheme[1].get("basic_fsi", 0),
                "incentive_fsi": best_scheme[1].get("incentive_fsi", 0),
                "max_bua_sqft": best_scheme[1].get("max_bua_sqft", 0),
            },
            "eligibility_criteria": self._get_eligibility_criteria(),
            "submission_requirements": self._get_submission_requirements(),
            "terms_and_conditions": self._get_terms_conditions(),
            "evaluation_criteria": self._get_evaluation_criteria(),
        }

        return tender

    def _get_eligibility_criteria(self) -> List[str]:
        return [
            "RERA registration mandatory",
            "Minimum 5 years of experience in Maharashtra",
            "Completed at least 2 residential projects of similar scale",
            "No pending RERA complaints",
            "Financial capability: Minimum net worth of Rs. 5 Crores",
            "No criminal cases against company/directors",
        ]

    def _get_submission_requirements(self) -> List[str]:
        return [
            "Technical Bid with project plan",
            "Financial bid with detailed BOQ",
            "RERA registration certificate",
            "Company registration documents",
            "Experience certificates",
            "Financial statements (3 years)",
            "Bank guarantee of Rs. 5 lakhs",
        ]

    def _get_terms_conditions(self) -> List[str]:
        return [
            "Tender validity: 90 days",
            "Security deposit: 2% of project cost",
            "Performance guarantee: 5% of project cost",
            "Timeline: As per schedule submitted",
            "RERA carpet area commitment binding",
        ]

    def _get_evaluation_criteria(self) -> Dict:
        return {
            "technical_score": {
                "experience": 25,
                "financial_capability": 20,
                "project_plan": 25,
                "compliance_record": 15,
                "innovation": 15,
            },
            "financial_score": {
                "revenue_share": 40,
                "timeline": 30,
                "construction_quality": 30,
            },
            "weightage": {"technical": 0.6, "financial": 0.4},
        }


# Deemed Conveyance Document Checklist
DEEMED_CONVEYANCE_DOCS = [
    {
        "id": 1,
        "name": "Society Registration Certificate",
        "description": "Certificate of registration under Maharashtra Cooperative Societies Act",
        "source": "Society",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 2,
        "name": "Original Share Certificates",
        "description": "All original share certificates of members",
        "source": "Society",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 3,
        "name": "Occupation Certificate (OC)",
        "description": "OC for existing building",
        "source": "MCGM/Builder",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 4,
        "name": "Index-II Extract",
        "description": "Land ownership history",
        "source": "Sub-Registrar",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 5,
        "name": "7/12 Extract / Property Card",
        "description": "Land ownership details",
        "source": "Tahsildar",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 6,
        "name": "Development Agreement",
        "description": "Agreement with developer (if applicable)",
        "source": "Society/Builder",
        "mandatory": False,
        "status": "pending",
    },
    {
        "id": 7,
        "name": "NOC from Existing Tenants",
        "description": "No Objection Certificates",
        "source": "Tenants",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 8,
        "name": "Building Plan Approval",
        "description": "MCGM approved building plans",
        "source": "MCGM",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 9,
        "name": "Structural Stability Certificate",
        "description": "Certificate for old building",
        "source": "Structural Engineer",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 10,
        "name": "Fire NOC",
        "description": "No Objection Certificate from Fire Department",
        "source": "Fire Department",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 11,
        "name": "Encumbrance Certificate",
        "description": "No encumbrances on property",
        "source": "Sub-Registrar",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 12,
        "name": "List of Allottees",
        "description": "Details of all flat owners",
        "source": "Society",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 13,
        "name": "Maintenance Statement",
        "description": "Society maintenance records",
        "source": "Society",
        "mandatory": False,
        "status": "pending",
    },
    {
        "id": 14,
        "name": "Architect Certificate",
        "description": "Building area certificate",
        "source": "Architect",
        "mandatory": True,
        "status": "pending",
    },
    {
        "id": 15,
        "name": "Survey Plan",
        "description": "Property boundary survey",
        "source": "Licensed Surveyor",
        "mandatory": True,
        "status": "pending",
    },
]


# CLI Functions
def cmd_fetch_property(args):
    """Fetch property data from all sources"""
    aggregator = PropertyDataAggregator()
    data = aggregator.get_complete_property_data(args.cts_no, args.village)
    print(f"\nProperty Data for {args.cts_no}:")
    print(json.dumps(asdict(data), indent=2, default=str))


def cmd_generate_feasibility(args):
    """Generate feasibility report"""
    generator = FeasibilityReportGenerator()
    report = generator.generate_from_cts(args.cts_no, args.village)

    print(f"\nFeasibility Report Generated: {report['report_id']}")
    print("\nFSI Analysis:")
    for scheme, config in report["fsi_analysis"].items():
        print(
            f"  {scheme}: Basic={config['basic_fsi']}, Incentive={config['incentive_fsi']}, "
            f"Total={config['total_fsi']}, Max BUA={config['max_bua_sqft']} sq.ft."
        )

    print(f"\nRecommendation: {report['recommendation']}")

    if args.output:
        output_file = Path(args.output) / f"feasibility_{report['report_id']}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nReport saved to: {output_file}")


def cmd_generate_tender(args):
    """Generate tender document"""
    # Load feasibility report
    feas_file = Path(args.feasibility_report)
    if feas_file.exists():
        report = json.loads(feas_file.read_text())
    else:
        print("Generating feasibility report first...")
        generator = FeasibilityReportGenerator()
        report = generator.generate_from_cts(args.feasibility_report, "")

    generator = TenderGenerator()
    tender = generator.generate_tender(report, args.type)

    print(f"\nTender Generated: {tender['tender_id']}")
    print(f"Type: {tender['type']}")
    print(
        f"Property: {tender['property']['cts_no']} ({tender['property']['plot_area_sq_m']} sq.m)"
    )
    print(f"Scheme: {tender['scheme']['name']} (FSI: {tender['scheme']['total_fsi']})")

    if args.output:
        output_file = Path(args.output) / f"tender_{tender['tender_id']}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(tender, indent=2, default=str))
        print(f"\nTender saved to: {output_file}")


def cmd_list_compliances(args):
    """List all compliance regulations"""
    compliance_ds = ComplianceDataSource()
    regs = compliance_ds.fetch_compliances(
        args.scheme if hasattr(args, "scheme") else ""
    )

    print("\nApplicable Compliances:")
    print("-" * 80)
    for r in regs:
        print(f"{r.regulation_id}: {r.title}")
        print(f"  Category: {r.category}")
        print(f"  Source: {r.source}")
        print(f"  Effective: {r.effective_date}")
        print()


def cmd_list_deemed_docs(args):
    """List deemed conveyance documents"""
    print("\nDeemed Conveyance Document Checklist:")
    print("=" * 80)
    for doc in DEEMED_CONVEYANCE_DOCS:
        status = "✓" if doc["status"] == "ready" else "○"
        mand = "REQUIRED" if doc["mandatory"] else "OPTIONAL"
        print(f"{status} [{mand}] {doc['id']}. {doc['name']}")
        print(f"    {doc['description']}")
        print(f"    Source: {doc['source']}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Government Data Sources")
    subparsers = parser.add_subparsers(dest="cmd")

    # Fetch property
    fetch_parser = subparsers.add_parser("fetch", help="Fetch property data")
    fetch_parser.add_argument("cts_no", help="CTS/Survey number")
    fetch_parser.add_argument("--village", default="", help="Village name")

    # Feasibility report
    feas_parser = subparsers.add_parser(
        "feasibility", help="Generate feasibility report"
    )
    feas_parser.add_argument("cts_no", help="CTS/Survey number")
    feas_parser.add_argument("--village", default="", help="Village name")
    feas_parser.add_argument("--output", default="reports/", help="Output directory")

    # Tender
    tender_parser = subparsers.add_parser("tender", help="Generate tender")
    tender_parser.add_argument(
        "feasibility_report", help="Feasibility report file or CTS no"
    )
    tender_parser.add_argument(
        "--type", default="e_tender", choices=["e_tender", "traditional"]
    )
    tender_parser.add_argument("--output", default="reports/", help="Output directory")

    # List compliances
    subparsers.add_parser("compliances", help="List compliance regulations")

    # Deemed conveyance docs
    subparsers.add_parser("deemed-docs", help="List deemed conveyance documents")

    args = parser.parse_args()

    if args.cmd == "fetch":
        cmd_fetch_property(args)
    elif args.cmd == "feasibility":
        cmd_generate_feasibility(args)
    elif args.cmd == "tender":
        cmd_generate_tender(args)
    elif args.cmd == "compliances":
        cmd_list_compliances(args)
    elif args.cmd == "deemed-docs":
        cmd_list_deemed_docs(args)
    else:
        parser.print_help()
