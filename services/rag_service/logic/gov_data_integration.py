#!/usr/bin/env python3
"""
Government Data Integration - Hybrid Mode
API when available, OCR/Document Upload when API fails
"""

import os
import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PropertyData:
    """Property data from any source"""

    survey_no: str = ""
    cts_no: str = ""

    # Area
    plot_area_sq_m: float = 0.0
    plot_area_sq_ft: float = 0.0

    # Location
    village: str = ""
    taluka: str = ""
    district: str = ""

    # Zone & DP
    zone_type: str = ""
    dp_remarks: str = ""
    road_width_m: float = 0.0

    # Building
    max_height_m: float = 0.0
    max_floors: int = 0

    # Ownership
    tenure: str = ""
    owners: list = None

    # Metadata
    data_source: str = ""
    fetch_method: str = ""  # api, ocr, manual
    fetched_at: datetime = None
    confidence: float = 0.0  # 0-1, how confident we are in the data
    verification_status: str = "pending"  # pending, verified, unverified


class GovernmentDataIntegration:
    """
    Hybrid government data integration
    - Try APIs first (Bhulekh, BMC, NOCAS)
    - Fall back to OCR document upload
    - Allow manual entry with validation
    """

    def __init__(self):
        self.api_available = self._check_api_connectivity()
        self.saved_data_dir = DATA_DIR / "verified_properties"
        self.saved_data_dir.mkdir(parents=True, exist_ok=True)

    def _check_api_connectivity(self) -> bool:
        """Check if government APIs are reachable"""
        import socket
        import requests

        sites = [
            ("bhulekh.maharashtra.gov.in", 443),
            ("property.mcgm.gov.in", 443),
            ("nocas.mahaonline.gov.in", 443),
        ]

        for host, port in sites:
            try:
                socket.create_connection((host, port), timeout=3)
                return True
            except:
                continue

        # Check if we can reach any government site
        try:
            r = requests.get("https://www.maharashtra.gov.in", timeout=5)
            return r.status_code == 200
        except:
            return False

    def get_property_data(
        self,
        survey_no: str,
        district: str = "Mumbai Suburban",
        taluka: str = "",
        village: str = "",
    ) -> PropertyData:
        """
        Get property data - tries API first, falls back to OCR/Manual
        """
        result = PropertyData(survey_no=survey_no)
        result.fetched_at = datetime.now()

        if self.api_available:
            # Try API integrations
            api_data = self._fetch_from_apis(survey_no, district, taluka, village)
            if api_data:
                result = self._merge_api_data(result, api_data)
                result.fetch_method = "api"
                result.confidence = 0.9  # High confidence from official API
                result.verification_status = "verified"
                return result

        # Check if we have verified data saved locally
        local_data = self._load_saved_data(survey_no)
        if local_data:
            return local_data

        # Fall back to OCR/manual entry
        result.fetch_method = "manual_required"
        result.confidence = 0.0
        result.verification_status = "pending"
        result.dp_remarks = (
            "⚠️ Please provide one of:\n"
            "1. Upload Property Card PDF for OCR\n"
            "2. Upload 7/12 extract\n"
            "3. Enter details manually"
        )
        return result

    def _fetch_from_apis(
        self, survey_no: str, district: str, taluka: str, village: str
    ) -> Optional[Dict]:
        """Fetch from government APIs"""
        # This would call the actual API integrations
        # For now, return None since APIs aren't reachable
        return None

    def _merge_api_data(self, result: PropertyData, api_data: Dict) -> PropertyData:
        """Merge API data into result"""
        for key, value in api_data.items():
            if hasattr(result, key):
                setattr(result, key, value)
        return result

    def _load_saved_data(self, survey_no: str) -> Optional[PropertyData]:
        """Load previously verified data"""
        safe_id = survey_no.replace("/", "_")
        file_path = self.saved_data_dir / f"{safe_id}.json"

        if file_path.exists():
            data = json.loads(file_path.read_text())
            result = PropertyData(**data)
            result.fetch_method = "verified_upload"
            result.confidence = 1.0
            result.verification_status = "verified"
            return result

        return None

    def save_verified_data(self, data: PropertyData):
        """Save verified property data"""
        safe_id = data.survey_no.replace("/", "_")
        file_path = self.saved_data_dir / f"{safe_id}.json"
        file_path.write_text(json.dumps(asdict(data), indent=2, default=str))

    def process_uploaded_document(
        self, file_path: str, doc_type: str
    ) -> Optional[Dict]:
        """
        Process uploaded document (Property Card, 7/12, etc.)
        Uses OCR to extract data
        """
        from .property_card_workflow import PropertyCardOCR

        ocr = PropertyCardOCR()

        if doc_type == "property_card":
            # Try PDF first
            if file_path.lower().endswith(".pdf"):
                cards = ocr.extract_from_pdf(file_path)
                if cards:
                    card = cards[0]
                    return {
                        "survey_no": card.survey_no,
                        "plot_area_sq_m": card.plot_area_sq_m,
                        "plot_area_sq_ft": card.plot_area_sq_ft,
                        "zone_type": card.zone_type,
                        "road_width_m": card.road_width_m,
                        "village": card.village,
                        "taluka": card.taluka,
                        "district": card.district,
                        "extraction_confidence": 0.8,
                        "source": "ocr_property_card",
                    }
            else:
                # Image file
                card = ocr.extract_from_image(file_path)
                return {
                    "survey_no": card.survey_no,
                    "plot_area_sq_m": card.plot_area_sq_m,
                    "plot_area_sq_ft": card.plot_area_sq_ft,
                    "zone_type": card.zone_type,
                    "road_width_m": card.road_width_m,
                    "extraction_confidence": 0.7,
                    "source": "ocr_image",
                }

        elif doc_type == "7_12":
            # 7/12 extract - extract text and parse
            return self._parse_7_12(file_path)

        return None

    def _parse_7_12(self, file_path: str) -> Dict:
        """Parse 7/12 extract document"""
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        # Extract key fields
        result = {
            "source": "7_12_extract",
            "extraction_confidence": 0.85,
            "raw_text": text[:1000],  # First 1000 chars
        }

        # Parse survey number
        import re

        survey_match = re.search(r"Survey No[.\s]*[:]?\s*([\d/]+)", text, re.I)
        if survey_match:
            result["survey_no"] = survey_match.group(1)

        # Parse area
        area_match = re.search(
            r"(\d+[\.,]?\d*)\s*(Sq\.?\s*m|Hectare|Acre|Guntha)", text, re.I
        )
        if area_match:
            area_str = area_match.group(1).replace(",", "")
            area_type = area_match.group(2).lower()
            area = float(area_str)

            if "hectare" in area_type:
                result["plot_area_sq_m"] = area * 10000
            elif "acre" in area_type:
                result["plot_area_sq_m"] = area * 4046.86
            elif "guntha" in area_type:
                result["plot_area_sq_m"] = area * 101.17
            else:
                result["plot_area_sq_m"] = area

        return result

    def manual_entry(self, data: Dict) -> PropertyData:
        """Create property data from manual entry"""
        result = PropertyData(
            survey_no=data.get("survey_no", ""),
            cts_no=data.get("cts_no", ""),
            plot_area_sq_m=float(data.get("plot_area_sq_m", 0)),
            plot_area_sq_ft=float(data.get("plot_area_sq_ft", 0)),
            village=data.get("village", ""),
            taluka=data.get("taluka", ""),
            district=data.get("district", ""),
            zone_type=data.get("zone_type", "Residential"),
            dp_remarks=data.get("dp_remarks", ""),
            road_width_m=float(data.get("road_width_m", 9)),
            max_height_m=float(data.get("max_height_m", 0)),
            tenure=data.get("tenure", "Freehold"),
            data_source="manual",
            fetch_method="manual",
            fetched_at=datetime.now(),
            confidence=0.6,  # Lower confidence for manual
            verification_status="pending",
        )

        # Calculate derived fields
        if result.plot_area_sq_ft == 0 and result.plot_area_sq_m > 0:
            result.plot_area_sq_ft = result.plot_area_sq_m * 10.764

        return result


# WhatsApp Integration for Compliance Updates
class WhatsAppComplianceReader:
    """
    Read WhatsApp messages for compliance updates
    """

    def __init__(self):
        self.compliance_file = (
            DATA_DIR / "data_sources" / "compliance" / "regulations.json"
        )
        self.compliance_file.parent.mkdir(parents=True, exist_ok=True)

    def parse_message(
        self, message: str, sender: str = "", timestamp: str = ""
    ) -> Optional[Dict]:
        """
        Parse WhatsApp message for compliance updates
        """
        import re

        # Patterns for government notifications
        patterns = [
            # MahaRERA circular
            r"(?i)(maharera|maha\s*RERA).*?(circular|order|notification|guideline)\s*[:\-]?\s*(.+)",
            # DCPR/Regulation updates
            r"(?i)(DCPR|DCR|mumbai).*?(regulation|amendment|new\s*rule)\s*[:\-]?\s*(.+)",
            # MCGM notice
            r"(?i)(mcgm|municipal).*?(notice|order|amendment)\s*[:\-]?\s*(.+)",
            # Government notification
            r"(?i)(govt|government|maharashtra).*?(notification|order)\s*[:\-]?\s*(.+)",
            # Effective date mentions
            r"(?i)(effective|from)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*[:\-]?\s*(.+)",
            # FSI/Building rule changes
            r"(?i)(FSI|FAR|building\s*permission).*?(changed|amended|new)\s*[:\-]?\s*(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.I | re.M)
            if match:
                groups = match.groups()

                return {
                    "regulation_id": f"WA_{datetime.now().strftime('%Y%m%d%H%M')}",
                    "title": self._extract_title(groups),
                    "description": message.strip(),
                    "effective_date": self._extract_date(groups, message),
                    "source": f"WhatsApp - {sender}",
                    "source_timestamp": timestamp,
                    "category": self._categorize(groups),
                    "applicability": ["all"],
                    "requires_action": True,
                    "raw_match": match.group(0),
                }

        return None

    def _extract_title(self, groups: tuple) -> str:
        """Extract title from match groups"""
        for g in reversed(groups):
            if g and len(g.strip()) > 10:
                return g.strip()[:100]
        return "Imported from WhatsApp"

    def _extract_date(self, groups: tuple, full_text: str) -> str:
        """Extract effective date"""
        import re

        date_pattern = r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}"
        match = re.search(date_pattern, full_text)
        if match:
            return match.group(0)
        return datetime.now().strftime("%Y-%m-%d")

    def _categorize(self, groups: tuple) -> str:
        """Categorize the compliance type"""
        text = " ".join(g for g in groups if g)

        if "rera" in text.lower():
            return "rera"
        elif "dcpr" in text.lower() or "fsi" in text.lower():
            return "dcpr"
        elif "fire" in text.lower():
            return "fire"
        elif "environment" in text.lower():
            return "environment"
        else:
            return "general"

    def add_compliance(self, compliance: Dict) -> bool:
        """Add compliance to database"""
        try:
            if self.compliance_file.exists():
                data = json.loads(self.compliance_file.read_text())
            else:
                data = []

            # Check for duplicates
            for existing in data:
                if existing.get("title") == compliance.get("title"):
                    return False  # Already exists

            data.append(compliance)
            self.compliance_file.write_text(json.dumps(data, indent=2))
            return True
        except:
            return False

    def import_from_chat_export(self, chat_file: str) -> int:
        """Import compliances from WhatsApp chat export file"""
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse WhatsApp export format
            # Format: "12/31/2024, 10:30 AM - Sender: Message"
            import re

            pattern = r"(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}\s*(?:AM|PM))?\s*-\s*([^:]+):\s*(.+)"

            matches = re.findall(pattern, content, re.MULTILINE)

            count = 0
            for match in matches:
                date, time, sender, message = match
                timestamp = f"{date} {time or ''}".strip()

                compliance = self.parse_message(message, sender.strip(), timestamp)
                if compliance:
                    if self.add_compliance(compliance):
                        count += 1

            return count
        except Exception as e:
            logger.error(f"Import error: {e}", exc_info=True)
            return 0


# API Endpoints for Data Integration
def add_data_endpoints(app):
    """Add data integration endpoints to FastAPI app"""
    from fastapi import HTTPException, UploadFile, File, Form
    from typing import Optional

    integration = GovernmentDataIntegration()
    whatsapp_reader = WhatsAppComplianceReader()

    @app.post("/api/property/{survey_no}")
    async def get_property(
        survey_no: str,
        district: str = "Mumbai Suburban",
        taluka: str = "",
        village: str = "",
    ):
        """Get property data from all sources"""
        try:
            data = integration.get_property_data(survey_no, district, taluka, village)
            return asdict(data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/property/{survey_no}/upload")
    async def upload_property_document(
        survey_no: str, doc_type: str = Form(...), file: UploadFile = File(...)
    ):
        """Upload property document for OCR extraction"""
        try:
            # Save uploaded file
            upload_dir = UPLOADS_DIR / survey_no.replace("/", "_")
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = upload_dir / file.filename
            content = await file.read()
            file_path.write_bytes(content)

            # Process with OCR
            result = integration.process_uploaded_document(str(file_path), doc_type)

            if result:
                return {
                    "success": True,
                    "extracted_data": result,
                    "file_path": str(file_path),
                }
            else:
                return {
                    "success": False,
                    "message": "Could not extract data from document",
                }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/property/{survey_no}/manual")
    async def manual_property_entry(survey_no: str, data: Dict):
        """Manual property data entry"""
        try:
            data["survey_no"] = survey_no
            result = integration.manual_entry(data)
            integration.save_verified_data(result)
            return asdict(result)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/compliance/whatsapp")
    async def import_whatsapp_compliance(chat_file: UploadFile = File(...)):
        """Import compliances from WhatsApp chat export"""
        try:
            # Save chat file
            chat_path = (
                UPLOADS_DIR / f"chat_{datetime.now().strftime('%Y%m%d%H%M')}.txt"
            )
            content = await chat_file.read()
            chat_path.write_bytes(content)

            # Import
            count = whatsapp_reader.import_from_chat_export(str(chat_path))

            return {
                "success": True,
                "compliances_imported": count,
                "file": str(chat_path),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/compliance/pending")
    async def get_pending_compliances():
        """Get compliances that need review"""
        try:
            compliance_file = (
                DATA_DIR / "data_sources" / "compliance" / "regulations.json"
            )
            if compliance_file.exists():
                data = json.loads(compliance_file.read_text())
                pending = [c for c in data if c.get("requires_action", False)]
                return pending
            return []
        except:
            return []

    return app


if __name__ == "__main__":
    # Test the integration
    integration = GovernmentDataIntegration()

    logger.info("Government Data Integration")
    logger.info("=" * 50)
    logger.info(f"API Available: {integration.api_available}")
    logger.info("")

    # Get property data
    data = integration.get_property_data(
        "123/456", "Mumbai Suburban", "Andheri", "Andheri"
    )

    logger.info(f"Survey No: {data.survey_no}")
    logger.info(f"Fetch Method: {data.fetch_method}")
    logger.info(f"Confidence: {data.confidence}")
    logger.info(f"Verification: {data.verification_status}")
    logger.info("")
    logger.info("DP Remarks / Next Steps:")
    logger.info(data.dp_remarks)

