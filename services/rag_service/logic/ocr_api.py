#!/usr/bin/env python3
"""
OCR Document Upload and Processing API
Handles property card and 7-12 extract uploads
"""

import os
import json
import re
import uuid
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
EXTRACTED_DIR = DATA_DIR / "extracted"
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="OCR Document Processing API")


@dataclass
class ExtractedPropertyData:
    """Extracted property data from documents"""

    document_id: str
    document_type: str  # property_card, 7_12, index_ii
    extracted_at: datetime

    # Property details
    survey_no: str = ""
    plot_area_sq_m: float = 0.0
    plot_area_sq_ft: float = 0.0
    road_width_m: float = 0.0
    zone_type: str = ""
    village: str = ""
    taluka: str = ""
    district: str = ""
    tenure: str = ""

    # Ownership
    owners: List[str] = None

    # Metadata
    confidence: float = 0.0
    raw_text: str = ""
    status: str = "pending"  # pending, verified, rejected


class OCRProcessor:
    """OCR processing for property documents"""

    def __init__(self):
        self.easyocr_available = False
        self._init_ocr()

    def _init_ocr(self):
        """Initialize OCR engine"""
        try:
            import easyocr

            self.reader = easyocr.Reader(["en", "mr"], gpu=False, verbose=False)
            self.easyocr_available = True
            logger.info("EasyOCR initialized")
        except ImportError:
            logger.warning("EasyOCR not available, using basic text extraction")

    def process_image(self, image_path: str) -> ExtractedPropertyData:
        """Process property card image"""
        doc_id = str(uuid.uuid4())[:8]
        result = ExtractedPropertyData(
            document_id=doc_id,
            document_type="property_card",
            extracted_at=datetime.now(),
        )

        if not self.easyocr_available:
            result.status = "error"
            result.raw_text = "OCR not available"
            return result

        try:
            # Read text from image
            texts = self.reader.readtext(image_path, detail=0)
            full_text = "\n".join(texts)
            result.raw_text = full_text[:5000]  # Limit storage

            # Extract data
            self._extract_property_data(full_text, result)

            result.confidence = 0.75
            result.status = "extracted"

        except Exception as e:
            result.status = "error"
            result.raw_text = str(e)

        return result

    def process_pdf(self, pdf_path: str) -> List[ExtractedPropertyData]:
        """Process PDF document (may contain multiple pages)"""
        from pypdf import PdfReader

        results = []

        try:
            reader = PdfReader(pdf_path)

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()

                doc_id = f"{uuid.uuid4().hex[:8]}_{page_num}"
                result = ExtractedPropertyData(
                    document_id=doc_id,
                    document_type=self._detect_doc_type(text),
                    extracted_at=datetime.now(),
                )
                result.raw_text = text[:5000]

                self._extract_property_data(text, result)
                result.confidence = 0.8
                result.status = "extracted"

                if result.survey_no:  # Only add if we found data
                    results.append(result)

        except Exception as e:
            logger.error(f"PDF processing error: {e}", exc_info=True)

        return results

    def _detect_doc_type(self, text: str) -> str:
        """Detect document type from text"""
        text_upper = text.upper()

        if "7/12" in text_upper or "सात बारा" in text or "7-12" in text_upper:
            return "7_12"
        elif "INDEX-II" in text_upper or "INDEX II" in text_upper:
            return "index_ii"
        elif "PROPERTY CARD" in text_upper:
            return "property_card"
        elif "7/12" in text or "७/१२" in text:
            return "7_12"
        else:
            return "unknown"

    def _extract_property_data(self, text: str, result: ExtractedPropertyData):
        """Extract property data from text"""

        # Survey number patterns
        patterns = [
            r"Survey\s*(?:No\.?|Number)?\s*[:\-]?\s*([\d/]+)",
            r"S\.?N\.?\s*[:\-]?\s*([\d/]+)",
            r"CTS\s*(?:No\.?)?\s*[:\-]?\s*([\d/]+)",
            r"Plot\s*(?:No\.?)?\s*[:\-]?\s*([\d/]+)",
            r"गाव\s*[:\-]?\s*([^\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                result.survey_no = match.group(1).strip()
                break

        # Area in sq.m
        area_patterns = [
            r"(\d+[\.,]?\d*)\s*(?:Sq\.?|Square)?\s*(?:Meter|M\.?|m\.?)\s*(?:sq\.?)?",
            r"क्षेत्रफळ\s*[:\-]?\s*([\d\.]+)",
            r"Area\s*[:\-]?\s*([\d\.,]+)\s*(?:Sq\.?|Square)?",
        ]

        for pattern in area_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    area_str = match.group(1).replace(",", "")
                    result.plot_area_sq_m = float(area_str)
                    result.plot_area_sq_ft = result.plot_area_sq_m * 10.764
                    break
                except:
                    pass

        # Road width
        road_match = re.search(r"(\d+\.?\d*)\s*m\.?\s*(?:Road|R/?W|W\b)", text, re.I)
        if road_match:
            result.road_width_m = float(road_match.group(1))

        # Zone type
        if re.search(r"\bResidential\b", text, re.I):
            result.zone_type = "Residential"
        elif re.search(r"\bCommercial\b", text, re.I):
            result.zone_type = "Commercial"
        elif re.search(r"\bIndustrial\b", text, re.I):
            result.zone_type = "Industrial"

        # Village
        village_match = re.search(
            r"Village\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|Taluka)", text, re.I
        )
        if village_match:
            result.village = village_match.group(1).strip()

        # Taluka
        taluka_match = re.search(
            r"Taluka\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|District)", text, re.I
        )
        if taluka_match:
            result.taluka = taluka_match.group(1).strip()

        # District
        district_match = re.search(
            r"District\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|Pin)", text, re.I
        )
        if district_match:
            result.district = district_match.group(1).strip()

        # Tenure
        if re.search(r"\bFreehold\b", text, re.I):
            result.tenure = "Freehold"
        elif re.search(r"\bLeasehold\b", text, re.I):
            result.tenure = "Leasehold"
        elif re.search(r"\bN\.?A\.?\b", text, re.I):
            result.tenure = "N.A."

        # Owners (extract names)
        owner_patterns = [
            r"Owner\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"नाव\s*[:\-]?\s*(.+?)(?:\n|$)",
        ]

        result.owners = []
        for pattern in owner_patterns:
            matches = re.findall(pattern, text, re.I)
            result.owners.extend([m.strip() for m in matches[:5]])  # Limit to 5 owners


# Global processor
processor = OCRProcessor()


@app.post("/api/ocr/property-card")
async def process_property_card(file: UploadFile = File(...)):
    """
    Upload and process property card image/PDF
    """
    try:
        # Save uploaded file
        file_id = uuid.uuid4().hex[:8]
        extension = Path(file.filename).suffix.lower()

        upload_dir = UPLOADS_DIR / "property_cards"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / f"{file_id}{extension}"

        content = await file.read()
        file_path.write_bytes(content)

        # Process based on file type
        if extension in [".pdf"]:
            results = processor.process_pdf(str(file_path))

            # Save extracted data
            for result in results:
                save_extracted_data(result)

            return {
                "success": True,
                "document_id": file_id,
                "pages_processed": len(results),
                "extracted_data": [asdict(r) for r in results],
            }

        else:  # Image file
            result = processor.process_image(str(file_path))
            save_extracted_data(result)

            return {
                "success": True,
                "document_id": file_id,
                "extracted_data": asdict(result),
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ocr/7-12")
async def process_7_12(file: UploadFile = File(...)):
    """
    Upload and process 7-12 extract PDF
    """
    try:
        file_id = uuid.uuid4().hex[:8]
        extension = ".pdf"

        upload_dir = UPLOADS_DIR / "7_12"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / f"{file_id}{extension}"

        content = await file.read()
        file_path.write_bytes(content)

        results = processor.process_pdf(str(file_path))

        for result in results:
            result.document_type = "7_12"
            save_extracted_data(result)

        return {
            "success": True,
            "document_id": file_id,
            "pages_processed": len(results),
            "extracted_data": [asdict(r) for r in results],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ocr/verify/{document_id}")
async def verify_extracted_data(document_id: str, verified_data: Dict):
    """
    Verify and correct extracted data
    """
    extracted_file = EXTRACTED_DIR / f"{document_id}.json"

    if not extracted_file.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    data = json.loads(extracted_file.read_text())
    data.update(verified_data)
    data["status"] = "verified"
    data["verified_at"] = datetime.now().isoformat()

    extracted_file.write_text(json.dumps(data, indent=2))

    return {"success": True, "message": "Data verified and saved"}


@app.get("/api/ocr/status/{document_id}")
async def get_ocr_status(document_id: str):
    """Get extraction status"""
    extracted_file = EXTRACTED_DIR / f"{document_id}.json"

    if not extracted_file.exists():
        return {"status": "not_found"}

    data = json.loads(extracted_file.read_text())
    return {
        "status": data.get("status"),
        "confidence": data.get("confidence"),
        "survey_no": data.get("survey_no"),
        "area": data.get("plot_area_sq_m"),
    }


def save_extracted_data(result: ExtractedPropertyData):
    """Save extracted data to file"""
    file_path = EXTRACTED_DIR / f"{result.document_id}.json"
    file_path.write_text(json.dumps(asdict(result), indent=2, default=str))


@app.get("/api/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "ocr_available": processor.easyocr_available,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    logger.info("Starting OCR API Server...")
    logger.info("API Documentation: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)

