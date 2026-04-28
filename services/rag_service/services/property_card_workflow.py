#!/usr/bin/env python3
"""
Property Card OCR and Report Generator
Extracts data from property cards and generates LandWise-style reports
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import OCR libraries
EASYOCR_AVAILABLE = False
try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    pass

TRACTOR_AVAILABLE = False
try:
    TTRACTOR_AVAILABLE = False
except ImportError:
    pass


@dataclass
class PropertyCard:
    """Property card data structure"""

    survey_no: str = ""
    plot_area_sq_m: float = 0.0
    plot_area_sq_ft: float = 0.0
    existing_structure_area_sq_ft: float = 0.0
    road_width_m: float = 0.0
    zone_type: str = ""  # Residential, Commercial, etc.
    landowner_name: str = ""
    address: str = ""
    village: str = ""
    taluka: str = ""
    district: str = ""
    pincode: str = ""
    latitude: float = 0.0
    longitude: float = 0.0


@dataclass
class FSIConfiguration:
    """FSI configuration for a scheme"""

    scheme_name: str = ""
    basic_fsi: float = 0.0
    incentive_fsi: float = 0.0
    premium_fsi: float = 0.0
    tdr_fsi: float = 0.0
    max_permissible_fsi: float = 0.0
    fungible_fsi: float = 0.0
    in_situ_fsi: float = 0.0


@dataclass
class CostBreakdown:
    """Cost breakdown structure"""

    land_costs: float = 0.0
    approval_costs: float = 0.0
    construction_costs: float = 0.0
    sales_marketing: float = 0.0
    developer_fees: float = 0.0

    # Detailed breakdown
    land_cost: float = 0.0
    corpus_fund: float = 0.0
    total_rent: float = 0.0
    shifting_charges: float = 0.0
    stamp_duty: float = 0.0
    gst_rehab: float = 0.0
    tdr_cost: float = 0.0

    scrutiny_fees_layout: float = 0.0
    scrutiny_fees_building: float = 0.0
    scrutiny_fees_tdr: float = 0.0
    iod_deposit: float = 0.0
    debris_removal: float = 0.0
    excavation_royalty: float = 0.0
    premium_fsi_charges: float = 0.0
    development_charges_plot: float = 0.0
    development_charges_bua: float = 0.0
    fungible_fsi_charges: float = 0.0
    staircase_lift_premium: float = 0.0
    open_space_deficiency: float = 0.0
    development_cess: float = 0.0
    labour_welfare_cess: float = 0.0
    infrastructure_charges: float = 0.0


@dataclass
class RevenueBreakdown:
    """Revenue structure"""

    residential_area_sqft: float = 0.0
    residential_rate_per_sqft: float = 0.0
    office_area_sqft: float = 0.0
    office_rate_per_sqft: float = 0.0
    retail_area_sqft: float = 0.0
    retail_rate_per_sqft: float = 0.0
    parking_slots: int = 0
    parking_rate_per_slot: float = 0.0
    discounted_rehab_residential: float = 0.0
    discounted_rehab_commercial: float = 0.0
    dr_generated_sqm: float = 0.0
    dr_rate_per_sqm: float = 0.0


@dataclass
class ProjectAnalysis:
    """Complete project analysis"""

    project_name: str = ""
    property_card: PropertyCard = None
    selected_scheme: str = ""
    fsi_config: FSIConfiguration = None
    cost_breakdown: CostBreakdown = None
    revenue: RevenueBreakdown = None

    # Computed values
    total_bua_sqft: float = 0.0
    rera_carpet_sqft: float = 0.0
    rehab_area_sqft: float = 0.0
    saleable_area_sqft: float = 0.0

    total_revenue_cr: float = 0.0
    total_cost_cr: float = 0.0
    gross_profit_cr: float = 0.0
    net_profit_cr: float = 0.0
    gross_margin_pct: float = 0.0
    net_margin_pct: float = 0.0


class PropertyCardOCR:
    """OCR system for property cards"""

    def __init__(self, use_gpu: bool = False):
        self.reader = None
        if EASYOCR_AVAILABLE:
            self.reader = easyocr.Reader(["en"], gpu=use_gpu)
            logger.info("EasyOCR initialized")
        else:
            logger.warning("EasyOCR not available. Install with: pip install easyocr")

    def extract_from_image(self, image_path: str) -> PropertyCard:
        """Extract property card data from image"""
        if not self.reader:
            raise RuntimeError("OCR reader not initialized")

        result = self.reader.readtext(image_path)

        card = PropertyCard()

        for detection in result:
            text = detection[1].upper()
            detection[2]

            # Extract survey number
            if "SURVEY" in text or "SY NO" in text or "CTS NO" in text:
                match = re.search(r"(\d+[\/\-\d]*)", text)
                if match:
                    card.survey_no = match.group(1)

            # Extract area
            area_match = re.search(r"(\d+[\.\d]*)\s*(sq\.?\s*m|sqm|sq\.?\s*ft|sqft)", text, re.I)
            if area_match and "AREA" in text:
                if "sq.m" in text.lower() or "sqm" in text.lower():
                    card.plot_area_sq_m = float(area_match.group(1))
                else:
                    card.plot_area_sq_ft = float(area_match.group(1))

            # Extract road width
            if "ROAD" in text and ("WIDTH" in text or "W" in text):
                match = re.search(r"(\d+\.?\d*)\s*m", text)
                if match:
                    card.road_width_m = float(match.group(1))

            # Extract zone
            if "ZONE" in text:
                if "RESIDENTIAL" in text:
                    card.zone_type = "Residential"
                elif "COMMERCIAL" in text:
                    card.zone_type = "Commercial"
                elif "INDUSTRIAL" in text:
                    card.zone_type = "Industrial"

            # Extract location
            if "VILLAGE" in text or "VILL" in text:
                parts = text.split()
                for i, p in enumerate(parts):
                    if "VILL" in p:
                        if i + 1 < len(parts):
                            card.village = parts[i + 1]

            if "TALUKA" in text:
                parts = text.split()
                for i, p in enumerate(parts):
                    if "TALUKA" in p:
                        if i + 1 < len(parts):
                            card.taluka = parts[i + 1]

            if "DISTRICT" in text:
                parts = text.split()
                for i, p in enumerate(parts):
                    if "DISTRICT" in p:
                        if i + 1 < len(parts):
                            card.district = parts[i + 1]

        # Convert sq.m to sq.ft if needed
        if card.plot_area_sq_m > 0 and card.plot_area_sq_ft == 0:
            card.plot_area_sq_ft = card.plot_area_sq_m * 10.764

        return card

    def extract_from_pdf(self, pdf_path: str) -> list[PropertyCard]:
        """Extract property card data from PDF"""
        from pypdf import PdfReader

        cards = []
        reader = PdfReader(pdf_path)

        for page in reader.pages:
            text = page.extract_text()
            card = self._parse_text(text)
            if card.survey_no:
                cards.append(card)

        return cards

    def _parse_text(self, text: str) -> PropertyCard:
        """Parse extracted text into PropertyCard"""
        card = PropertyCard()
        text_upper = text.upper()

        # Survey number
        patterns = [
            r"SURVEY\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*(\d+[\/\-\d]*)",
            r"SY\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*(\d+[\/\-\d]*)",
            r"CTS\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*(\d+[\/\-\d]*)",
            r"PLOT\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*(\d+[\/\-\d]*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                card.survey_no = match.group(1)
                break

        # Area in sq.m
        match = re.search(r"(\d+[\.,]\d+)\s*(?:Sq\.?|Square)?\s*(?:Meter|M\.?)", text, re.I)
        if match:
            card.plot_area_sq_m = float(match.group(1).replace(",", ""))

        # Area in sq.ft
        match = re.search(
            r"(\d+[\.,]\d+)\s*(?:Sq\.?|Square)?\s*(?:Foot|Feet|Ft\.?|Sq\.?\s*Ft)",
            text,
            re.I,
        )
        if match:
            card.plot_area_sq_ft = float(match.group(1).replace(",", ""))

        # Road width
        match = re.search(r"(\d+\.?\d*)\s*(?:M\.?|Meter)", text_upper)
        if "ROAD" in text_upper or "WIDTH" in text_upper:
            card.road_width_m = float(match.group(1)) if match else 0

        # Zone type
        if "RESIDENTIAL" in text_upper:
            card.zone_type = "Residential"
        elif "COMMERCIAL" in text_upper:
            card.zone_type = "Commercial"
        elif "INDUSTRIAL" in text_upper:
            card.zone_type = "Industrial"
        elif "AGRICULTURAL" in text_upper:
            card.zone_type = "Agricultural"

        # Village
        match = re.search(r"VILLAGE[:\s]+([A-Za-z\s]+?)(?:,|\n|Taluka)", text, re.I)
        if match:
            card.village = match.group(1).strip()

        # Taluka
        match = re.search(r"TALUKA[:\s]+([A-Za-z\s]+?)(?:,|\n|District)", text, re.I)
        if match:
            card.taluka = match.group(1).strip()

        # District
        match = re.search(r"DISTRICT[:\s]+([A-Za-z\s]+?)(?:,|\n|Pin)", text, re.I)
        if match:
            card.district = match.group(1).strip()

        # Existing structure area
        match = re.search(
            r"EXISTING\s*(?:STRUCTURE|BUILDING|CONSTRUCTION)\s*(?:AREA)?[:\s]+(\d+[\.,]\d*)",
            text_upper,
        )
        if match:
            card.existing_structure_area_sq_ft = float(match.group(1).replace(",", ""))

        return card


class DCPRCalculator:
    """DCPR 2034 FSI Calculator"""

    def __init__(self, rag_agent=None):
        self.rag_agent = rag_agent
        self.schemes = {
            "33(20B)": {
                "name": "Optimum Utilization (33-20B)",
                "basic_fsi": 2.5,
                "max_fsi": 4.0,
                "incentive_fsi": 0.0,
                "premium_fsi": 0.5,
                "tdr_permissible": True,
                "fungible_fsi": 0.2,
                "notes": "For plots >500sq.m, no incentive for affordable housing",
            },
            "33(11)": {
                "name": "FSI Loading (33-11)",
                "basic_fsi": 1.0,
                "max_fsi": 4.0,
                "incentive_fsi": 0.0,
                "premium_fsi": 0.5,
                "tdr_permissible": True,
                "fungible_fsi": 0.2,
                "notes": "FSI loaded, incentive for affordable housing component",
            },
            "33(7B)": {
                "name": "Incentive Based (33-7B)",
                "basic_fsi": 0.5,
                "max_fsi": 4.0,
                "incentive_fsi": 0.15,
                "premium_fsi": 0.5,
                "tdr_permissible": True,
                "fungible_fsi": 0.2,
                "notes": "Must include 70% affordable housing for incentive",
            },
            "30(A)": {
                "name": "DP Road Frontage (30-A)",
                "basic_fsi": 2.5,
                "max_fsi": 4.0,
                "incentive_fsi": 0.0,
                "premium_fsi": 0.5,
                "tdr_permissible": True,
                "fungible_fsi": 0.2,
                "notes": "Additional FSI for DP road setback surrender",
            },
        }

    def calculate_scheme(
        self,
        scheme_id: str,
        plot_area_sq_m: float,
        road_width_m: float,
        zone_type: str,
        affordable_housing_pct: float = 0.0,
    ) -> FSIConfiguration:
        """Calculate FSI for a scheme"""
        if scheme_id not in self.schemes:
            raise ValueError(f"Unknown scheme: {scheme_id}")

        scheme = self.schemes[scheme_id]
        config = FSIConfiguration(scheme_name=scheme["name"])

        # Basic FSI
        config.basic_fsi = scheme["basic_fsi"]

        # Incentive FSI (for 33(7B))
        if scheme_id == "33(7B)" and affordable_housing_pct >= 70:
            config.incentive_fsi = scheme["incentive_fsi"]

        # Premium FSI (optional)
        config.premium_fsi = 0.5  # 50% premium

        # TDR FSI (optional)
        config.tdr_fsi = 0.9  # Up to 90%

        # Max Permissible FSI
        config.max_permissible_fsi = scheme["max_fsi"]

        # Fungible FSI
        config.fungible_fsi = scheme["fungible_fsi"]

        # In-situ FSI (for road setback)
        if scheme_id == "30(A)" and road_width_m >= 9:
            config.in_situ_fsi = 2.0

        return config

    def get_applicable_schemes(self, plot_area_sq_m: float, zone_type: str) -> list[str]:
        """Get applicable schemes for a property"""
        schemes = []

        for scheme_id, _scheme in self.schemes.items():
            if plot_area_sq_m >= 500 or scheme_id in ["33(7B)", "33(11)"]:
                schemes.append(scheme_id)

        return schemes

    def query_dcpr(self, query: str, k: int = 5) -> list[str]:
        """Query DCPR regulations using RAG"""
        if not self.rag_agent:
            return []

        results = self.rag_agent.vectorstore.search(query, k=k)
        return [text for score, text in results]


class ReportGenerator:
    """Generate LandWise-style reports"""

    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)

    def generate_scheme_comparison(self, analysis: ProjectAnalysis, schemes: list[str]) -> str:
        """Generate scheme comparison table"""
        output = []
        output.append("=" * 80)
        output.append("SCHEME COMPARISON REPORT")
        output.append(f"Project: {analysis.project_name}")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        output.append("=" * 80)
        output.append("")

        # Headers
        headers = ["Parameter", "Unit"] + schemes
        col_widths = [40, 10] + [15] * len(schemes)

        # Print headers
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths, strict=False))
        output.append(header_line)
        output.append("-" * len(header_line))

        # Plot area
        row = ["Plot Area for FSI Calculation", "sq.m"]
        for _scheme in schemes:
            row.append(f"{analysis.property_card.plot_area_sq_m:,.2f}")
        output.append(" | ".join(r.ljust(w) for r, w in zip(row, col_widths, strict=False)))

        # FSI Statement
        output.append("")
        output.append("FSI Statement:")

        # Basic FSI
        row = ["Zonal Basic FSI", "Ratio"]
        for _scheme in schemes:
            row.append(f"{DCPRCalculator().schemes.get(_scheme, {}).get('basic_fsi', 0):.2f}")
        output.append(" | ".join(r.ljust(w) for r, w in zip(row, col_widths, strict=False)))

        # Max Permissible
        row = ["Max Permissible FSI", "Ratio"]
        for _scheme in schemes:
            row.append(f"{DCPRCalculator().schemes.get(_scheme, {}).get('max_fsi', 0):.2f}")
        output.append(" | ".join(r.ljust(w) for r, w in zip(row, col_widths, strict=False)))

        output.append("")
        return "\n".join(output)

    def generate_financial_summary(self, analysis: ProjectAnalysis) -> str:
        """Generate financial summary report"""
        output = []
        output.append("=" * 80)
        output.append("FINANCIAL SUMMARY REPORT")
        output.append(f"Project: {analysis.project_name}")
        output.append(f"Scheme: {analysis.selected_scheme}")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        output.append("=" * 80)
        output.append("")

        # Area Summary
        output.append("AREA SUMMARY (Saleable RERA Carpet)")
        output.append("-" * 40)
        output.append(f"Residential:    {analysis.revenue.residential_area_sqft:,.0f} sq.ft.")
        output.append(f"Office:         {analysis.revenue.office_area_sqft:,.0f} sq.ft.")
        output.append(f"Retail:         {analysis.revenue.retail_area_sqft:,.0f} sq.ft.")
        output.append(f"Parking Slots:  {analysis.revenue.parking_slots}")
        output.append("")

        # Revenue Summary
        output.append("REVENUE SUMMARY")
        output.append("-" * 40)
        residential_rev = (
            analysis.revenue.residential_area_sqft
            * analysis.revenue.residential_rate_per_sqft
            / 10000000
        )
        output.append(f"Residential:    ₹{residential_rev:,.2f} Cr")

        office_rev = (
            analysis.revenue.office_area_sqft * analysis.revenue.office_rate_per_sqft / 10000000
        )
        output.append(f"Office:         ₹{office_rev:,.2f} Cr")

        retail_rev = (
            analysis.revenue.retail_area_sqft * analysis.revenue.retail_rate_per_sqft / 10000000
        )
        output.append(f"Retail:         ₹{retail_rev:,.2f} Cr")

        parking_rev = (
            analysis.revenue.parking_slots * analysis.revenue.parking_rate_per_slot / 10000000
        )
        output.append(f"Parking:        ₹{parking_rev:,.2f} Cr")

        output.append("-" * 40)
        output.append(f"TOTAL REVENUE:  ₹{analysis.total_revenue_cr:,.2f} Cr")
        output.append("")

        # Cost Summary
        output.append("COST SUMMARY")
        output.append("-" * 40)
        output.append(f"Land/ Land Related Costs:  ₹{analysis.cost_breakdown.land_costs:,.2f} Cr")
        output.append(
            f"Approval Costs:           ₹{analysis.cost_breakdown.approval_costs:,.2f} Cr"
        )
        output.append(
            f"Construction Costs:        ₹{analysis.cost_breakdown.construction_costs:,.2f} Cr"
        )
        output.append(
            f"Sales & Marketing:         ₹{analysis.cost_breakdown.sales_marketing:,.2f} Cr"
        )
        output.append(
            f"Developer Fees:           ₹{analysis.cost_breakdown.developer_fees:,.2f} Cr"
        )
        output.append("-" * 40)
        output.append(f"TOTAL COST:               ₹{analysis.total_cost_cr:,.2f} Cr")
        output.append("")

        # Profitability
        output.append("PROFITABILITY ANALYSIS")
        output.append("-" * 40)
        output.append(
            f"Gross Profit:      ₹{analysis.gross_profit_cr:,.2f} Cr ({analysis.gross_margin_pct:.1f}%)"
        )
        output.append(
            f"Net Profit:        ₹{analysis.net_profit_cr:,.2f} Cr ({analysis.net_margin_pct:.1f}%)"
        )
        output.append(
            f"Cost per sq.ft.:   ₹{analysis.total_cost_cr * 10000000 / analysis.rera_carpet_sqft:,.0f}/sq.ft."
        )
        output.append("")

        return "\n".join(output)

    def generate_approval_cost_summary(self, analysis: ProjectAnalysis) -> str:
        """Generate detailed approval cost summary"""
        output = []
        output.append("=" * 80)
        output.append("APPROVAL COST SUMMARY")
        output.append(f"Project: {analysis.project_name}")
        output.append(f"Scheme: {analysis.selected_scheme}")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        output.append("=" * 80)
        output.append("")

        cb = analysis.cost_breakdown

        output.append("{:50} {:>15}".format("Particulars", "Amount (₹)"))
        output.append("-" * 65)

        output.append("Scrutiny Fees:")
        output.append("{:50} ₹{:>12,}".format("  Layout Scrutiny Fees", cb.scrutiny_fees_layout))
        output.append(
            "{:50} ₹{:>12,}".format("  Building Plan Scrutiny", cb.scrutiny_fees_building)
        )
        output.append("{:50} ₹{:>12,}".format("  TDR Utilization Fees", cb.scrutiny_fees_tdr))

        output.append("")
        output.append("Deposits:")
        output.append("{:50} ₹{:>12,}".format("  IOD Deposit", cb.iod_deposit))
        output.append("{:50} ₹{:>12,}".format("  Debris Removal Deposit", cb.debris_removal))
        output.append("{:50} ₹{:>12,}".format("  Excavation Royalty", cb.excavation_royalty))

        output.append("")
        output.append("Premium Charges:")
        output.append("{:50} ₹{:>12,}".format("  Premium FSI Charges", cb.premium_fsi_charges))
        output.append("{:50} ₹{:>12,}".format("  Fungible FSI Charges", cb.fungible_fsi_charges))
        output.append(
            "{:50} ₹{:>12,}".format("  Staircase/Lift Premium", cb.staircase_lift_premium)
        )
        output.append("{:50} ₹{:>12,}".format("  Open Space Deficiency", cb.open_space_deficiency))

        output.append("")
        output.append("Development Charges:")
        output.append("{:50} ₹{:>12,}".format("  On Plot Area", cb.development_charges_plot))
        output.append("{:50} ₹{:>12,}".format("  On BUA", cb.development_charges_bua))

        output.append("")
        output.append("Cess & Other:")
        output.append("{:50} ₹{:>12,}".format("  Development Cess", cb.development_cess))
        output.append("{:50} ₹{:>12,}".format("  Labour Welfare Cess", cb.labour_welfare_cess))
        output.append(
            "{:50} ₹{:>12,}".format("  Infrastructure Charges", cb.infrastructure_charges)
        )

        output.append("-" * 65)
        output.append("{:50} ₹{:>12,}".format("TOTAL APPROVAL COSTS", cb.approval_costs))
        output.append("")

        return "\n".join(output)

    def export_to_pdf(self, analysis: ProjectAnalysis, output_path: str, report_type: str = "all"):
        """Export report to PDF"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            doc = SimpleDocTemplate(output_path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph(f"<b>{analysis.project_name}</b>", styles["Title"]))
            elements.append(Paragraph(f"Scheme: {analysis.selected_scheme}", styles["Normal"]))
            elements.append(Spacer(1, 0.3 * inch))

            if report_type in ["financial", "all"]:
                elements.append(Paragraph("<b>FINANCIAL SUMMARY</b>", styles["Heading1"]))
                elements.append(Spacer(1, 0.1 * inch))

                rev = analysis.revenue
                area_data = [
                    ["Type", "Area (sq.ft.)"],
                    ["Residential", f"{rev.residential_area_sqft:,.0f}"],
                    ["Office", f"{rev.office_area_sqft:,.0f}"],
                    ["Retail", f"{rev.retail_area_sqft:,.0f}"],
                    ["Parking Slots", f"{rev.parking_slots}"],
                ]
                t = Table(area_data, colWidths=[2 * inch, 2 * inch])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                            (
                                "BACKGROUND",
                                (0, 1),
                                (-1, -1),
                                colors.HexColor("#ecf0f1"),
                            ),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                elements.append(t)
                elements.append(Spacer(1, 0.2 * inch))

                rev_data = [
                    ["Source", "Amount (₹ Cr)"],
                    ["Residential", f"{analysis.total_revenue_cr * 0.98:.2f}"],
                    ["Parking", f"{analysis.total_revenue_cr * 0.02:.2f}"],
                    ["TOTAL REVENUE", f"{analysis.total_revenue_cr:.2f}"],
                ]
                t = Table(rev_data, colWidths=[2 * inch, 2 * inch])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            (
                                "BACKGROUND",
                                (0, 1),
                                (-1, -2),
                                colors.HexColor("#d5f4e6"),
                            ),
                            (
                                "BACKGROUND",
                                (0, -1),
                                (-1, -1),
                                colors.HexColor("#27ae60"),
                            ),
                            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                elements.append(t)
                elements.append(Spacer(1, 0.2 * inch))

                cb = analysis.cost_breakdown
                cost_data = [
                    ["Category", "Amount (₹ Cr)"],
                    ["Land/ Land Related", f"{cb.land_costs / 10000000:.2f}"],
                    ["Approval Costs", f"{cb.approval_costs / 10000000:.2f}"],
                    ["Construction", f"{cb.construction_costs / 10000000:.2f}"],
                    ["Sales & Marketing", f"{cb.sales_marketing / 10000000:.2f}"],
                    ["Developer Fees", f"{cb.developer_fees / 10000000:.2f}"],
                    ["TOTAL COST", f"{analysis.total_cost_cr:.2f}"],
                ]
                t = Table(cost_data, colWidths=[2 * inch, 2 * inch])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            (
                                "BACKGROUND",
                                (0, 1),
                                (-1, -2),
                                colors.HexColor("#fdedec"),
                            ),
                            (
                                "BACKGROUND",
                                (0, -1),
                                (-1, -1),
                                colors.HexColor("#e74c3c"),
                            ),
                            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                elements.append(t)
                elements.append(Spacer(1, 0.2 * inch))

                profit_color = (
                    colors.HexColor("#27ae60")
                    if analysis.net_profit_cr > 0
                    else colors.HexColor("#e74c3c")
                )
                profit_data = [
                    ["Metric", "Value"],
                    [
                        "Gross Profit",
                        f"₹{analysis.gross_profit_cr:.2f} Cr ({analysis.gross_margin_pct:.1f}%)",
                    ],
                    [
                        "Net Profit",
                        f"₹{analysis.net_profit_cr:.2f} Cr ({analysis.net_margin_pct:.1f}%)",
                    ],
                    [
                        "Cost per sq.ft.",
                        f"₹{analysis.total_cost_cr * 10000000 / analysis.rera_carpet_sqft:,.0f}",
                    ],
                ]
                t = Table(profit_data, colWidths=[2 * inch, 3 * inch])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), profit_color),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 10),
                            (
                                "BACKGROUND",
                                (0, 1),
                                (-1, -1),
                                colors.HexColor("#f8f9fa"),
                            ),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                elements.append(t)

            doc.build(elements)
            return output_path

        except ImportError:
            txt_path = output_path.replace(".pdf", ".txt")
            with open(txt_path, "w") as f:
                if report_type == "financial":
                    f.write(self.generate_financial_summary(analysis))
                elif report_type == "approval":
                    f.write(self.generate_approval_cost_summary(analysis))
                elif report_type == "scheme":
                    f.write(
                        self.generate_scheme_comparison(
                            analysis, ["33(20B)", "33(11)", "33(7B)", "30(A)"]
                        )
                    )
                else:
                    f.write(self.generate_financial_summary(analysis))
                    f.write("\n\n")
                    f.write(self.generate_approval_cost_summary(analysis))
            return txt_path


class PropertyCardWorkflow:
    """Main workflow for property card analysis"""

    def __init__(self, rag_agent=None):
        self.ocr = PropertyCardOCR() if EASYOCR_AVAILABLE else None
        self.calculator = DCPRCalculator(rag_agent)
        self.generator = ReportGenerator()
        self.rag_agent = rag_agent

    def analyze_from_card(
        self,
        card: PropertyCard,
        schemes: list[str] = None,
        revenue: RevenueBreakdown = None,
        costs: CostBreakdown = None,
        affordable_housing_pct: float = 0.0,
    ) -> ProjectAnalysis:
        """Full analysis from property card"""

        analysis = ProjectAnalysis()
        analysis.property_card = card
        analysis.project_name = f"Property Analysis - {card.survey_no}"

        if schemes is None:
            schemes = self.calculator.get_applicable_schemes(card.plot_area_sq_m, card.zone_type)

        # Calculate for each scheme
        best_scheme = None
        best_fsi = 0

        for scheme in schemes:
            config = self.calculator.calculate_scheme(
                scheme,
                card.plot_area_sq_m,
                card.road_width_m,
                card.zone_type,
                affordable_housing_pct=affordable_housing_pct,
            )

            total_fsi = config.basic_fsi + config.incentive_fsi
            if total_fsi > best_fsi:
                best_fsi = total_fsi
                best_scheme = scheme

        analysis.selected_scheme = best_scheme

        # Set default revenue/costs if not provided
        if revenue is None:
            revenue = RevenueBreakdown()
            revenue.residential_area_sqft = card.plot_area_sq_ft * best_fsi * 0.8
            revenue.residential_rate_per_sqft = 25000  # Default rate
            revenue.parking_slots = int(card.plot_area_sq_ft / 500)

        if costs is None:
            costs = self._estimate_costs(card, best_scheme, revenue)

        analysis.revenue = revenue
        analysis.cost_breakdown = costs

        # Compute financials
        analysis.total_revenue_cr = (
            revenue.residential_area_sqft * revenue.residential_rate_per_sqft
            + revenue.office_area_sqft * revenue.office_rate_per_sqft
            + revenue.retail_area_sqft * revenue.retail_rate_per_sqft
            + revenue.parking_slots * revenue.parking_rate_per_slot
        ) / 10000000

        analysis.total_cost_cr = (
            costs.land_costs
            + costs.approval_costs
            + costs.construction_costs
            + costs.sales_marketing
            + costs.developer_fees
        ) / 10000000

        analysis.gross_profit_cr = analysis.total_revenue_cr - analysis.total_cost_cr
        analysis.gross_margin_pct = (
            (analysis.gross_profit_cr / analysis.total_revenue_cr * 100)
            if analysis.total_revenue_cr > 0
            else 0
        )

        # Net profit (after interest)
        interest_cost = costs.developer_fees * 0.5  # Estimate
        analysis.net_profit_cr = analysis.gross_profit_cr - (interest_cost / 10000000)
        analysis.net_margin_pct = (
            (analysis.net_profit_cr / analysis.total_revenue_cr * 100)
            if analysis.total_revenue_cr > 0
            else 0
        )

        analysis.rera_carpet_sqft = (
            revenue.residential_area_sqft + revenue.office_area_sqft + revenue.retail_area_sqft
        )

        return analysis

    def _estimate_costs(
        self, card: PropertyCard, scheme: str, revenue: RevenueBreakdown
    ) -> CostBreakdown:
        """Estimate costs based on property and scheme"""
        costs = CostBreakdown()

        plot_area = card.plot_area_sq_m

        # Land costs (rough estimates)
        costs.land_cost = 0
        costs.corpus_fund = plot_area * 50000  # ₹50,000 per sq.m
        costs.total_rent = revenue.residential_area_sqft * 50 * 12 * 5  # 5 years rent
        costs.shifting_charges = 1200000  # ₹12L fixed
        costs.stamp_duty = plot_area * 10000  # ₹10,000 per sq.m
        costs.gst_rehab = revenue.residential_area_sqft * 1500  # GST on rehab
        costs.tdr_cost = plot_area * 25000  # TDR cost

        costs.land_costs = (
            costs.land_cost
            + costs.corpus_fund
            + costs.total_rent
            + costs.shifting_charges
            + costs.stamp_duty
            + costs.gst_rehab
            + costs.tdr_cost
        )

        # Approval costs
        bua = revenue.residential_area_sqft / 10.764  # Convert to sq.m
        costs.scrutiny_fees_layout = 32400
        costs.scrutiny_fees_building = bua * 141
        costs.scrutiny_fees_tdr = plot_area * 100
        costs.iod_deposit = revenue.residential_area_sqft * 1
        costs.debris_removal = revenue.residential_area_sqft * 2
        costs.excavation_royalty = plot_area * 369
        costs.premium_fsi_charges = plot_area * 0.5 * 50000  # 50% premium FSI
        costs.development_charges_plot = plot_area * 1000
        costs.development_charges_bua = bua * 4000
        costs.fungible_fsi_charges = bua * 0.2 * 25000
        costs.staircase_lift_premium = bua * 5000
        costs.open_space_deficiency = plot_area * 20000
        costs.development_cess = bua * 1500
        costs.labour_welfare_cess = bua * 300
        costs.infrastructure_charges = plot_area * 500

        costs.approval_costs = (
            costs.scrutiny_fees_layout
            + costs.scrutiny_fees_building
            + costs.scrutiny_fees_tdr
            + costs.iod_deposit
            + costs.debris_removal
            + costs.excavation_royalty
            + costs.premium_fsi_charges
            + costs.development_charges_plot
            + costs.development_charges_bua
            + costs.fungible_fsi_charges
            + costs.staircase_lift_premium
            + costs.open_space_deficiency
            + costs.development_cess
            + costs.labour_welfare_cess
            + costs.infrastructure_charges
        )

        # Construction costs
        costs.construction_costs = revenue.residential_area_sqft * 35000  # ₹35,000 per sq.ft

        # Sales & Marketing (3% of revenue)
        total_revenue = (
            revenue.residential_area_sqft * revenue.residential_rate_per_sqft
            + revenue.office_area_sqft * revenue.office_rate_per_sqft
            + revenue.retail_area_sqft * revenue.retail_rate_per_sqft
            + revenue.parking_slots * revenue.parking_rate_per_slot
        )
        costs.sales_marketing = total_revenue * 0.03

        # Developer fees
        costs.developer_fees = costs.construction_costs * 0.15

        return costs

    def run_workflow(
        self, input_path: str, output_dir: str, report_types: list[str] = None
    ) -> dict[str, str]:
        """Run full workflow"""
        if report_types is None:
            report_types = ["scheme", "financial", "approval"]

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        outputs = {}

        # Extract property card
        if input_path.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
            if self.ocr:
                if input_path.lower().endswith(".pdf"):
                    cards = self.ocr.extract_from_pdf(input_path)
                else:
                    card = self.ocr.extract_from_image(input_path)
                    cards = [card]
            else:
                # Use text extraction only
                from pypdf import PdfReader

                reader = PdfReader(input_path)
                text = "\n".join(page.extract_text() for page in reader.pages)
                card = self.ocr._parse_text(text) if self.ocr else PropertyCard()
                cards = [card]
        else:
            raise ValueError(f"Unsupported file format: {input_path}")

        # Analyze each card
        for i, card in enumerate(cards):
            analysis = self.analyze_from_card(card)

            prefix = f"report_{card.survey_no or i + 1}"

            for report_type in report_types:
                output_path = output_dir / f"{prefix}_{report_type}.pdf"

                try:
                    self.generator.export_to_pdf(analysis, str(output_path), report_type)
                    outputs[report_type] = str(output_path)
                    logger.info(f"Generated: {output_path}")
                except Exception as e:
                    logger.error(f"Failed to generate {report_type}: {e}", exc_info=True)

        return outputs


class LandWiseReportParser:
    """Parse LandWise reports and extract structured data"""

    @staticmethod
    def parse_financial_summary(pdf_path: str) -> ProjectAnalysis:
        """Parse a LandWise Financial Summary PDF"""
        from pypdf import PdfReader

        analysis = ProjectAnalysis()
        reader = PdfReader(pdf_path)

        full_text = "\n".join(page.extract_text() for page in reader.pages)

        # Extract project name
        name_match = re.search(r"([\w\s]+)\s+\d+/\d+/\d+\s*$", full_text, re.MULTILINE)
        if name_match:
            analysis.project_name = name_match.group(1).strip()

        # Extract scheme
        scheme_match = re.search(r"under\s*-\s*(\d+\([^)]+\))", full_text, re.I)
        if scheme_match:
            analysis.selected_scheme = scheme_match.group(1)

        # Extract area
        area_match = re.search(r"Residential\s+([\d,]+)\s*sq\.ft", full_text)
        if area_match:
            revenue = RevenueBreakdown()
            revenue.residential_area_sqft = float(area_match.group(1).replace(",", ""))
            analysis.revenue = revenue

        # Extract parking
        parking_match = re.search(r"#\s*of\s*Parking\s*Lots\s+(\d+)", full_text)
        if parking_match and analysis.revenue:
            analysis.revenue.parking_slots = int(parking_match.group(1))

        # Extract revenue
        rev_match = re.search(r"Total Revenue\s+([\d.]+)\s*Cr", full_text)
        if rev_match:
            analysis.total_revenue_cr = float(rev_match.group(1))

        # Extract costs
        cost_match = re.search(r"Total Cost to Developer\s+([\d.]+)\s*Cr", full_text)
        if cost_match:
            analysis.total_cost_cr = float(cost_match.group(1))

        # Extract profits
        gross_match = re.search(r"Gross Profit\s+([\d.]+)\s*Cr", full_text)
        if gross_match:
            analysis.gross_profit_cr = float(gross_match.group(1))

        margin_match = re.search(r"Gross Profit Margin.*?(\d+)%", full_text)
        if margin_match:
            analysis.gross_margin_pct = float(margin_match.group(1))

        net_match = re.search(r"Net Profit\s+([\d.]+)\s*Cr", full_text)
        if net_match:
            analysis.net_profit_cr = float(net_match.group(1))

        net_margin_match = re.search(r"Net Profit Margin.*?(\d+)%", full_text)
        if net_margin_match:
            analysis.net_margin_pct = float(net_margin_match.group(1))

        return analysis

    @staticmethod
    def parse_scheme_comparison(pdf_path: str) -> dict:
        """Parse a LandWise Scheme Comparison PDF"""
        from pypdf import PdfReader

        schemes = {}
        reader = PdfReader(pdf_path)

        full_text = "\n".join(page.extract_text() for page in reader.pages)

        # Extract schemes from header
        scheme_names = re.findall(r"(33\([^)]+\))", full_text)

        # Extract plot area
        area_match = re.search(r"Plot Area.*?([\d,]+)\s*sq\.m", full_text)
        plot_area = float(area_match.group(1).replace(",", "")) if area_match else 0

        # Extract FSI for each scheme
        for scheme in set(scheme_names):
            patterns = {
                "basic_fsi": rf"{scheme}.*?Basic.*?(\d+\.?\d*)",
                "max_fsi": rf"{scheme}.*?Max.*?(\d+\.?\d*)",
            }
            for key, pattern in patterns.items():
                match = re.search(pattern, full_text, re.DOTALL | re.I)
                if match:
                    if scheme not in schemes:
                        schemes[scheme] = {}
                    schemes[scheme][key] = float(match.group(1))

        return {"schemes": schemes, "plot_area": plot_area}


# Example usage
if __name__ == "__main__":
    # Initialize workflow
    workflow = PropertyCardWorkflow()

    # Example property card
    card = PropertyCard(
        survey_no="123/P",
        plot_area_sq_m=2200,
        plot_area_sq_ft=23681,
        road_width_m=12,
        zone_type="Residential",
        village="Andheri",
        taluka="Andheri",
        district="Mumbai",
    )

    # Analyze
    analysis = workflow.analyze_from_card(card)

    # Print financial summary
    logger.info(workflow.generator.generate_financial_summary(analysis))
