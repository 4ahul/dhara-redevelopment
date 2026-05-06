"""
PDF Feasibility Report Builder
Generates a professional PDF mirroring the Globera Engineering format:
  - Cover page with letterhead
  - Enclosures table
  - Scope / Purpose / About Redevelopment
  - Property details
  - DCPR FSI table
  - Annexure I  — Existing Areas
  - Annexure II  — FSI Calculations (detailed)
  - Annexure III — Financial Calculations
  - Summary page
  - Conclusion & Notes

Uses reportlab Platypus for layout + Canvas for headers/footers.
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand colours (Globera-style) ─────────────────────────────────────────
NAVY = colors.HexColor("#1B3A6B")
GOLD = colors.HexColor("#C9A84C")
WHITE = colors.white
LIGHT = colors.HexColor("#EEF2F8")
MID = colors.HexColor("#D4E0F0")
GREEN = colors.HexColor("#1A6B3A")
LGREY = colors.HexColor("#F5F5F5")
DGREY = colors.HexColor("#444444")
BLACK = colors.black

W, H = A4  # 595 × 842 pts


# ── Style helpers ─────────────────────────────────────────────────────────
def styles():
    s = getSampleStyleSheet()
    base = {"fontName": "Helvetica", "fontSize": 9, "leading": 13, "textColor": BLACK}

    s.add(
        ParagraphStyle(
            "ReportTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            "SubTitle",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            "SecHead",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=4,
            underlineWidth=0.5,
        )
    )
    s.add(ParagraphStyle("Body", **base))
    s.add(
        ParagraphStyle(
            "BodyBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=BLACK,
        )
    )
    s.add(ParagraphStyle("Small", fontName="Helvetica", fontSize=7.5, leading=11, textColor=DGREY))
    s.add(
        ParagraphStyle(
            "CellHdr",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=WHITE,
            alignment=TA_CENTER,
        )
    )
    s.add(ParagraphStyle("CellBody", fontName="Helvetica", fontSize=8, leading=11, textColor=BLACK))
    s.add(
        ParagraphStyle(
            "CellNum",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=BLACK,
            alignment=TA_RIGHT,
        )
    )
    s.add(
        ParagraphStyle(
            "CellBoldNum",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=BLACK,
            alignment=TA_RIGHT,
        )
    )
    s.add(
        ParagraphStyle(
            "Footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=DGREY,
            alignment=TA_CENTER,
        )
    )
    s.add(
        ParagraphStyle(
            "ReportItalic",
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=DGREY,
        )
    )
    s.add(
        ParagraphStyle(
            "BulletBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=BLACK,
            leftIndent=12,
            bulletIndent=4,
            bulletFontName="Helvetica",
        )
    )
    return s


ST = styles()


def P(text, style="Body"):
    return Paragraph(str(text), ST[style])


def SP(pts):
    return Spacer(1, pts)


def HR():
    return HRFlowable(width="100%", thickness=0.5, color=MID, spaceAfter=4, spaceBefore=2)


# ── Table helpers ─────────────────────────────────────────────────────────
def hdr_cell(text):
    return Paragraph(str(text), ST["CellHdr"])


def body_cell(text):
    return Paragraph(str(text), ST["CellBody"])


def num_cell(text):
    return Paragraph(str(text), ST["CellNum"])


def bold_num(text):
    return Paragraph(str(text), ST["CellBoldNum"])


def cr(n):
    """Format as Indian crore string."""
    try:
        v = float(n)
        return f"{v:,.2f}"
    except Exception:
        return str(n)


def inr(n):
    """Format Indian number with commas."""
    try:
        v = int(float(n))
        return f"{v:,}"
    except Exception:
        return str(n)


def section_table_style(header_rows=1):
    return TableStyle(
        [
            # Header rows
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), WHITE),
            ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, header_rows - 1), 8),
            ("ALIGN", (0, 0), (-1, header_rows - 1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Body
            ("FONTNAME", (0, header_rows), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, header_rows), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C0CCDD")),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [WHITE, LGREY]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def subtotal_row_style(row_idx):
    return [
        ("BACKGROUND", (0, row_idx), (-1, row_idx), MID),
        ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
    ]


def total_row_style(row_idx):
    return [
        ("BACKGROUND", (0, row_idx), (-1, row_idx), NAVY),
        ("TEXTCOLOR", (0, row_idx), (-1, row_idx), WHITE),
        ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
    ]


# ── Section heading block ─────────────────────────────────────────────────
def sec_heading(title):
    tbl = Table([[P(title, "SecHead")]], colWidths=[W - 4 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, NAVY),
            ]
        )
    )
    return tbl


def annexure_banner(title, ref):
    tbl = Table([[P(title, "ReportTitle"), P(ref, "Small")]], colWidths=[W - 4 * cm - 80, 80])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return tbl


# ── Header / Footer canvas callback ───────────────────────────────────────
def on_page(canvas, doc, data):
    canvas.saveState()

    # Top thin navy bar
    canvas.setFillColor(NAVY)
    canvas.rect(
        doc.leftMargin,
        H - doc.topMargin + 4,
        W - doc.leftMargin - doc.rightMargin,
        3,
        fill=1,
        stroke=0,
    )

    # Society name top-right
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(NAVY)
    canvas.drawRightString(
        W - doc.rightMargin, H - doc.topMargin + 10, data.get("society_name", "")
    )

    # Bottom bar
    canvas.setFillColor(NAVY)
    canvas.rect(
        doc.leftMargin,
        doc.bottomMargin - 14,
        W - doc.leftMargin - doc.rightMargin,
        14,
        fill=1,
        stroke=0,
    )

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(WHITE)
    canvas.drawString(
        doc.leftMargin + 4,
        doc.bottomMargin - 9,
        "Globera Engineering Consultancy Pvt. Ltd.  •  98200 77939  •  contact@globera.in  •  www.globera.in",
    )
    canvas.drawRightString(
        W - doc.rightMargin - 4,
        doc.bottomMargin - 9,
        f"Feasibility Report  |  Page {doc.page}",
    )

    canvas.restoreState()


# ── Cover page ────────────────────────────────────────────────────────────
def build_cover(story, data):
    sp = SP

    # ── Header block ──
    title_tbl = Table(
        [
            [P("FEASIBILITY STUDY REPORT", "ReportTitle")],
            [P(data.get("society_name", ""), "SubTitle")],
        ],
        colWidths=[W - 4 * cm],
    )
    title_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), NAVY),
                ("BACKGROUND", (0, 1), (0, 1), GOLD),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(title_tbl)
    story.append(sp(16))

    # ── Letter content ──
    story.append(P(f"Ref. No.: {data.get('ref_no', '')}", "Body"))
    story.append(P(f"Date: {data.get('date', datetime.now().strftime('%d %B %Y'))}", "Body"))
    story.append(sp(12))

    story.append(P("To,", "Body"))
    story.append(P("The Hon. Sec. / Chairman,", "Body"))
    story.append(P(f"<b>{data.get('society_name', '')}</b>", "Body"))
    story.append(P(data.get("address_line1", ""), "Body"))
    story.append(P(data.get("address_line2", ""), "Body"))
    story.append(sp(10))

    story.append(
        P(
            f"<b>Sub:</b> Proposed Redevelopment of {data.get('society_name', '')}",
            "Body",
        )
    )
    story.append(P("<b>Reg.:</b> Feasibility Study.", "Body"))
    story.append(sp(10))

    story.append(P("Sir / Madam,", "Body"))
    story.append(sp(6))

    story.append(
        P(
            "We thank you for appointing us for the process of redevelopment of your society building and the "
            "project viability for proposed redevelopment of your building.",
            "Body",
        )
    )
    story.append(sp(6))

    story.append(
        P(
            f"The Study includes redevelopment of {data.get('society_short', data.get('society_name', ''))}. "
            "We have conducted a techno-economic study of the existing under Clause 33(7)(B), 33(11), 33(20)(B) "
            "and 33(12)(B) of Development Control and Promotion Rules, 2034. The study is conducted taking into "
            "consideration that existing Residential will be retained and the sale component available with the "
            "developer will be developed as residential cum commercial premises.",
            "Body",
        )
    )
    story.append(sp(6))

    story.append(
        P(
            "The project detailing is given under; the working of the project is as per the Annexures.",
            "Body",
        )
    )
    story.append(sp(10))
    story.append(P("We hope you find the above in proper order.", "Body"))
    story.append(P("Services, always at your behest.", "Body"))
    story.append(P("Thanking you,", "Body"))
    story.append(sp(20))
    story.append(P("For <b>Globera Engineering Consultancy Pvt. Ltd.</b>", "Body"))
    story.append(sp(30))
    story.append(P("<b>Sd/-</b>", "Body"))
    story.append(P("<b>MAYUR MERCHANT</b>", "Body"))

    story.append(PageBreak())


# ── Enclosures page ───────────────────────────────────────────────────────
def build_enclosures(story, data):
    story.append(sec_heading("Enclosures"))
    story.append(SP(8))

    rows = [
        [
            hdr_cell("Sr. No."),
            hdr_cell("Description"),
            hdr_cell("Scheme"),
            hdr_cell("Annexures"),
        ],
        [
            body_cell("1"),
            body_cell("Feasibility"),
            body_cell("33(7)(B), 33(11),\n33(12)(B) & 33(20)(B)"),
            body_cell(
                "Annexure I – 01 Page\nAnnexure II – 03 Pages\nAnnexure III – 04 Pages\nSummary – 01 Page"
            ),
        ],
        [
            body_cell("2"),
            body_cell("D.P. Remark"),
            body_cell(""),
            body_cell("02 Pages & 02 Plans"),
        ],
        [
            body_cell("3"),
            body_cell("T.P. Remark"),
            body_cell(""),
            body_cell("02 Pages & 01 Plan"),
        ],
        [
            body_cell("4"),
            body_cell("Superimpose of D.P. Remark over Plot Survey"),
            body_cell(""),
            body_cell("01 Page"),
        ],
        [
            body_cell("5"),
            body_cell("Superimpose of T.P. Remark over Plot Survey"),
            body_cell(""),
            body_cell("01 Page"),
        ],
    ]
    t = Table(rows, colWidths=[30, 180, 120, 165])
    t.setStyle(section_table_style())
    story.append(t)
    story.append(SP(12))
    story.append(PageBreak())


# ── Scope / Purpose / About / Documents pages ─────────────────────────────
def build_narrative(story, data):
    bullets = [
        "Collecting all the documents available with the society, which are pertinent for the actual "
        "verification of the title, ownership and the floor space status of the society.",
        "To verify the actual F.S.I. [Floor Space Index] consumed and the F.S.I. which can be loaded "
        "so as to achieve proper completion of the re-development project.",
        "To evaluate the project keeping in view the expectations of the members and future development; "
        "it will help us in gauging the project vis-à-vis minimum requirements of the members and the "
        "probability of the development.",
        "To give us an indication about the budget and thereby representing the actual funds required "
        "for the execution of the redevelopment.",
        "To indicate the potential of the project i.e. viability of the project, the minimum benefits "
        "that will come by to the members and if not then the expenses for carrying out the project.",
    ]

    story.append(sec_heading("Scope of the Feasibility Study"))
    story.append(SP(6))
    for b in bullets:
        story.append(P(f"• {b}", "BulletBody"))
        story.append(SP(2))

    story.append(SP(10))
    story.append(sec_heading("Purpose of the Feasibility Study"))
    story.append(SP(6))
    story.append(
        P(
            "A feasibility study is defined as an evaluation or analysis of the potential impact of a proposed "
            "project. A feasibility study is conducted to assist decision-makers in determining whether or not "
            "to implement the project. The feasibility study is based on extensive research on current trends "
            "and available resources. The extensive research, conducted in a non-biased manner, will provide "
            "data upon which to base a decision.",
            "Body",
        )
    )

    story.append(SP(10))
    story.append(sec_heading("About Redevelopment"))
    story.append(SP(6))
    story.append(
        P(
            "The term 'develop' means 'realise potentialities of land, especially by converting it for residential "
            "or industrial or commercial purposes'. Redevelopment, therefore, refers to the process of "
            "reconstruction of the residential / commercial / industrial premises by demolition of the existing "
            "structure and construction of a new structure. This is done by utilizing the maximum potential of "
            "the land by exploiting additional T.D.R., F.S.I. as specified under the Development Control and "
            "Promotion Rules 2034, of Municipal Corporation of Greater Mumbai.",
            "Body",
        )
    )

    story.append(SP(10))
    story.append(sec_heading("Chronicle and Particulars of the Existing Structure / Property"))
    story.append(SP(6))

    prop_rows = [
        [hdr_cell("Description"), hdr_cell("Details")],
        [body_cell("Property"), body_cell(data.get("property_desc", ""))],
        [body_cell("Location"), body_cell(data.get("location", ""))],
        [body_cell("Ward"), body_cell(data.get("ward", ""))],
        [body_cell("Zone (DP 2034)"), body_cell(data.get("zone", "Residential (R)"))],
        [
            body_cell("Existing Structures"),
            body_cell(
                f"Building A & Building B  |  {data.get('num_flats', 0)} Flats, {data.get('num_commercial', 0)} Commercial premises"
            ),
        ],
        [
            body_cell("Plot Area (Physical Survey)"),
            body_cell(f"{data.get('plot_area_sqm', 0):,.2f} Sq.m."),
        ],
        [
            body_cell("Road Width"),
            body_cell(f"{data.get('road_width_m', 0)} m (Swatantra Veer Savarkar Road)"),
        ],
        [body_cell("CRZ Status"), body_cell("CRZ II — NOC from MCZMA required")],
        [
            body_cell("Metro Rail Influence"),
            body_cell("Remarks from MMRDA to be obtained"),
        ],
    ]
    t = Table(prop_rows, colWidths=[160, 335])
    t.setStyle(section_table_style())
    story.append(t)
    story.append(SP(10))
    story.append(PageBreak())


# ── DCPR Technical Considerations + FSI summary table ────────────────────
def build_dcpr_fsi(story, data):
    story.append(sec_heading("D.C.P.R. Technical Considerations — FSI Computation"))
    story.append(SP(8))

    fsi = data.get("fsi", {})
    schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

    rows = [
        [hdr_cell("Description")] + [hdr_cell(s) for s in schemes],
        [body_cell("Road Width (m)")] + [body_cell("27.45 m") for _ in schemes],
        [body_cell("Zonal FSI")]
        + [num_cell(str(fsi.get(s, {}).get("zonal_fsi", 1.33))) for s in schemes],
        [body_cell("Additional F.S.I. Premium")]
        + [num_cell(str(fsi.get(s, {}).get("add_fsi_premium", "—"))) for s in schemes],
        [body_cell("Admissible TDR on road width")]
        + [num_cell(str(fsi.get(s, {}).get("tdr_road_width", "—"))) for s in schemes],
        [body_cell("Admissible F.S.I. (PTC)")]
        + [num_cell(str(fsi.get(s, {}).get("fsi_ptc", "—"))) for s in schemes],
        [body_cell("Additional F.S.I. 33(20)(B)")]
        + [num_cell(str(fsi.get(s, {}).get("add_fsi_2020b", "—"))) for s in schemes],
        [body_cell("Total FSI")]
        + [bold_num(str(fsi.get(s, {}).get("total_fsi", "—"))) for s in schemes],
        [body_cell("Fungible — 35%")]
        + [num_cell(str(fsi.get(s, {}).get("fungible", "—"))) for s in schemes],
        [body_cell("Total FSI Permissible")]
        + [bold_num(str(fsi.get(s, {}).get("total_fsi_permissible", "—"))) for s in schemes],
    ]

    t = Table(rows, colWidths=[160, 84, 84, 84, 84])
    ts = section_table_style()
    ts.add("ALIGN", (1, 1), (-1, -1), "CENTER")
    ts.add("BACKGROUND", (0, 7), (-1, 7), MID)
    ts.add("FONTNAME", (0, 7), (-1, 7), "Helvetica-Bold")
    ts.add("BACKGROUND", (0, 9), (-1, 9), NAVY)
    ts.add("TEXTCOLOR", (0, 9), (-1, 9), WHITE)
    ts.add("FONTNAME", (0, 9), (-1, 9), "Helvetica-Bold")
    t.setStyle(ts)
    story.append(t)
    story.append(SP(12))

    # BUA permissible table
    bua = data.get("bua", {})
    story.append(P("<b>Built-Up Area Permissible</b>", "Body"))
    story.append(SP(4))
    bua_rows = [
        [hdr_cell("Description")] + [hdr_cell(s) for s in schemes],
        [body_cell("Total Built-Up Area Permissible (Sq.ft.)")]
        + [bold_num(cr(bua.get(s, {}).get("total_bua_sqft", ""))) for s in schemes],
        [body_cell("Total RERA Carpet Area permissible (Sq.ft.)")]
        + [bold_num(cr(bua.get(s, {}).get("rera_carpet_sqft", ""))) for s in schemes],
        [body_cell("Number of Parking")]
        + [num_cell(str(bua.get(s, {}).get("parking", ""))) for s in schemes],
        [body_cell("Total Construction Area (Sq.ft.)")]
        + [num_cell(cr(bua.get(s, {}).get("total_constr_sqft", ""))) for s in schemes],
    ]
    t2 = Table(bua_rows, colWidths=[160, 84, 84, 84, 84])
    ts2 = section_table_style()
    ts2.add("ALIGN", (1, 1), (-1, -1), "RIGHT")
    for r in [1, 2]:
        ts2.add("BACKGROUND", (0, r), (-1, r), LIGHT)
        ts2.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
    t2.setStyle(ts2)
    story.append(t2)

    # Notes
    story.append(SP(10))
    story.append(sec_heading("Notes"))
    notes = [
        "Feasibility Study is only based as per data provided by Society — they are incomplete.",
        "Feasibility based on 33(23) (TOD FSI) not carried out as eligibility for the plot is not yet confirmed.",
        "As per DP 2034 online assessment, setbacks are shown on both sides of the road — DP Remarks required to ascertain.",
        "AutoCAD Plan of the Plot Survey / Total Station Survey was not shared — required.",
        "Approved BMC Plans provided are only for Building A — Building B plans required.",
        "The Land falls under Coastal Regulation Zone (CRZ) — CRZ II. NOC from MCZMA will be required.",
        "The plot abuts the proposed Metro Rail alignment / within influence zone. Remarks from MMRDA shall be obtained.",
        "Physical Area of Plot in possession of society is less than P.R. Card — setback appears to have been handed over to BMC.",
    ]
    for n in notes:
        story.append(P(f"• {n}", "ReportItalic"))
        story.append(SP(2))

    story.append(PageBreak())


# ── Annexure I — Existing Areas ───────────────────────────────────────────
def build_annexure_i(story, data):
    story.append(annexure_banner("ANNEXURE I : AREA", data.get("ref_no", "")))
    story.append(SP(10))

    # Commercial
    story.append(P("<b>Shops / Commercials</b>", "BodyBold"))
    story.append(SP(4))
    comm_rows = [
        [
            hdr_cell("Number"),
            hdr_cell("Nos."),
            hdr_cell("Area (Sq.m.)"),
            hdr_cell("Total (Sq.ft.)"),
        ],
    ]
    total_comm_sqft = 0
    for u in data.get("commercial_units", []):
        comm_rows.append(
            [
                body_cell(u.get("label", "")),
                num_cell(str(u.get("count", 1))),
                num_cell(f"{u.get('area_sqm', 0):.2f}"),
                num_cell(f"{u.get('total_sqft', 0):,.2f}"),
            ]
        )
        total_comm_sqft += u.get("total_sqft", 0)
    comm_rows.append(
        [
            bold_num("Area of Shops / Commercial"),
            bold_num(str(len(data.get("commercial_units", [])))),
            bold_num(""),
            bold_num(f"{total_comm_sqft:,.2f}"),
        ]
    )

    t = Table(comm_rows, colWidths=[200, 50, 100, 145])
    ts = section_table_style()
    ts.add("BACKGROUND", (0, -1), (-1, -1), GOLD)
    ts.add("TEXTCOLOR", (0, -1), (-1, -1), NAVY)
    t.setStyle(ts)
    story.append(t)
    story.append(SP(10))

    # Residential
    story.append(P("<b>Flats / Residential</b>", "BodyBold"))
    story.append(SP(4))
    res_rows = [
        [
            hdr_cell("Number"),
            hdr_cell("Nos."),
            hdr_cell("Area (Sq.m.)"),
            hdr_cell("Total (Sq.ft.)"),
        ],
    ]
    total_res_sqft = 0
    for u in data.get("residential_units", []):
        res_rows.append(
            [
                body_cell(u.get("label", "")),
                num_cell(str(u.get("count", 1))),
                num_cell(f"{u.get('area_sqm', 0):.2f}"),
                num_cell(f"{u.get('total_sqft', 0):,.2f}"),
            ]
        )
        total_res_sqft += u.get("total_sqft", 0)
    res_rows.append(
        [
            bold_num("Area of Residential"),
            bold_num(str(data.get("num_flats", 0))),
            bold_num(""),
            bold_num(f"{total_res_sqft:,.2f}"),
        ]
    )

    t2 = Table(res_rows, colWidths=[200, 50, 100, 145])
    ts2 = section_table_style()
    ts2.add("BACKGROUND", (0, -1), (-1, -1), GOLD)
    ts2.add("TEXTCOLOR", (0, -1), (-1, -1), NAVY)
    t2.setStyle(ts2)
    story.append(t2)

    story.append(SP(12))
    # Plot survey summary
    story.append(
        P(
            "<b>Plot Area — Superimpose of D.P. Remark and T.P. Remark over Plot Survey</b>",
            "BodyBold",
        )
    )
    story.append(SP(4))
    survey_rows = [
        [
            hdr_cell("Sr."),
            hdr_cell("Description"),
            hdr_cell("D.P. Remark (Sq.m.)"),
            hdr_cell("D.P. Remark (Sq.ft.)"),
            hdr_cell("T.P. Remark (Sq.m.)"),
            hdr_cell("T.P. Remark (Sq.ft.)"),
        ],
        [
            num_cell("1"),
            body_cell("Plot in Possession"),
            num_cell("1,367.74"),
            num_cell("14,722.21"),
            num_cell("1,360.76"),
            num_cell("14,647.08"),
        ],
        [
            num_cell("2"),
            body_cell("Plot under Setback"),
            num_cell("113.27"),
            num_cell("1,219.23"),
            num_cell("118.16"),
            num_cell("1,271.86"),
        ],
        [
            num_cell("3"),
            body_cell("Plot not in Possession"),
            num_cell("—"),
            num_cell("—"),
            num_cell("16.56"),
            num_cell("178.25"),
        ],
        [
            num_cell("4"),
            bold_num("Total Area of Plot as per Boundaries"),
            bold_num("1,481.01"),
            bold_num("15,941.44"),
            bold_num("1,495.48"),
            bold_num("16,097.20"),
        ],
        [
            num_cell("5"),
            body_cell("Plot in Adverse Possession"),
            num_cell("11.11"),
            num_cell("119.59"),
            num_cell("11.03"),
            num_cell("118.72"),
        ],
    ]
    t3 = Table(survey_rows, colWidths=[25, 170, 75, 75, 75, 75])
    ts3 = section_table_style()
    ts3.add("BACKGROUND", (0, 4), (-1, 4), NAVY)
    ts3.add("TEXTCOLOR", (0, 4), (-1, 4), WHITE)
    ts3.add("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold")
    t3.setStyle(ts3)
    story.append(t3)

    story.append(SP(8))
    story.append(
        P(
            "<b>Plot area considered for working:</b> Physical Survey (1,356.00 Sq.m.) + Area not in "
            "Possession per T.P. Remark (16.56 Sq.m.) = <b>Total 1,372.56 Sq.m.</b>",
            "Body",
        )
    )

    story.append(PageBreak())


# ── Annexure II — FSI (detailed) ──────────────────────────────────────────
def build_annexure_ii(story, data):
    story.append(annexure_banner("ANNEXURE II : FSI CALCULATION", data.get("ref_no", "")))
    story.append(SP(8))

    data.get("fsi", {})
    schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

    # Plot details header table
    pd_rows = [
        [
            hdr_cell("Plot Details"),
            hdr_cell(""),
            hdr_cell("Rate as per Ready Reckoner (₹)"),
            hdr_cell(""),
        ],
        [
            body_cell("Existing Commercial — Approved BUA"),
            num_cell("554.07 Sq.m. / 5,964 Sq.ft."),
            body_cell("R.C.C. Construction"),
            num_cell("₹30,250/Sq.m."),
        ],
        [
            body_cell("Existing Commercial — Carpet Area"),
            num_cell("494.71 Sq.m. / 5,325 Sq.ft."),
            body_cell("Open Land"),
            num_cell("₹1,99,670/Sq.m."),
        ],
        [
            body_cell("Existing Residential — Approved BUA"),
            num_cell("1,473.64 Sq.m. / 15,862 Sq.ft."),
            body_cell("Residential Building"),
            num_cell("₹3,87,500/Sq.m."),
        ],
        [
            body_cell("Existing Residential — Carpet Area"),
            num_cell("1,774.45 Sq.m. / 19,100 Sq.ft."),
            body_cell("Office/Commercial (upper floor)"),
            num_cell("₹4,61,560/Sq.m."),
        ],
        [
            body_cell("Number of Residential Units"),
            num_cell("28"),
            body_cell("Shop/Commercial (ground floor)"),
            num_cell("₹5,61,500/Sq.m."),
        ],
        [
            body_cell("Number of Commercial Units"),
            num_cell("18"),
            body_cell(""),
            num_cell(""),
        ],
    ]
    t = Table(pd_rows, colWidths=[175, 125, 155, 40])
    t.setStyle(section_table_style())
    story.append(t)
    story.append(SP(10))

    # Area of plot considered
    story.append(P("<b>Area of Plot Considered</b>", "BodyBold"))
    story.append(SP(4))
    plot_rows = [
        [hdr_cell("Source"), hdr_cell("Sq.m.")],
        [body_cell("Conveyance Deed"), num_cell("0.00")],
        [body_cell("P.R. Card"), num_cell("1,525.10")],
        [body_cell("Total Station Survey"), num_cell("1,356.00")],
        [body_cell("M.C.G.M. Plan"), num_cell("1,525.10")],
        [body_cell("T.P. Remarks"), num_cell("1,525.09")],
        [body_cell("D.P. Remarks"), num_cell("1,481.01")],
        [body_cell("Area not in Possession (T.P. Remark)"), num_cell("16.56")],
        [
            body_cell("Plot area considered (Physical + T.P. not-in-possession)"),
            bold_num("1,372.56"),
        ],
    ]
    t2 = Table(plot_rows, colWidths=[300, 195])
    ts2 = section_table_style()
    ts2.add("BACKGROUND", (0, -1), (-1, -1), NAVY)
    ts2.add("TEXTCOLOR", (0, -1), (-1, -1), WHITE)
    ts2.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    t2.setStyle(ts2)
    story.append(t2)
    story.append(SP(10))

    # Permissible BUA detailed
    bua = data.get("bua", {})
    story.append(P("<b>Built-Up Area Details (all schemes)</b>", "BodyBold"))
    story.append(SP(4))
    detail_rows = [
        [hdr_cell("Description")] + [hdr_cell(s) for s in schemes],
        [body_cell("Plot Under Development (Sq.m.)")] + [num_cell("1,372.56")] * 4,
        [body_cell("Zonal (Basic) FSI")] + [num_cell("1.33")] * 4,
        [body_cell("Built-up Area at Zonal FSI (Sq.m.)")] + [num_cell("1,825.50")] * 4,
        [body_cell("Additional BUA — FSI Premium (Sq.ft.)")]
        + [
            num_cell(cr(bua.get(s, {}).get("add_fsi_sqft", 12410.24 if s != "33(11)" else 0)))
            for s in schemes
        ],
        [body_cell("Additional BUA — TDR (Sq.ft.)")]
        + [
            num_cell(cr(bua.get(s, {}).get("tdr_sqft", 12262.50 if s != "33(11)" else 0)))
            for s in schemes
        ],
        [body_cell("Total Fungible Compensatory Area (Sq.m.)")]
        + [
            num_cell(
                cr(
                    bua.get(s, {}).get(
                        "fungible_total_sqm", 1247.26 if s == "33(7)(B)" else 1727.66
                    )
                )
            )
            for s in schemes
        ],
        [body_cell("Total Built-Up Area Permissible (Sq.ft.)")]
        + [bold_num(cr(bua.get(s, {}).get("total_bua_sqft", 0))) for s in schemes],
        [body_cell("Total RERA Carpet Area permissible (Sq.ft.)")]
        + [bold_num(cr(bua.get(s, {}).get("rera_carpet_sqft", 0))) for s in schemes],
        [body_cell("Staircase, Lift, Lobbies etc. (Sq.ft.)")]
        + [
            num_cell(
                cr(bua.get(s, {}).get("staircase_sqft", 8975.26 if s == "33(7)(B)" else 11967.02))
            )
            for s in schemes
        ],
        [body_cell("Yogalaya / Fitness Centre (Sq.ft.)")]
        + [
            num_cell(
                cr(bua.get(s, {}).get("yogalaya_sqft", 1196.70 if s == "33(7)(B)" else 1595.60))
            )
            for s in schemes
        ],
        [body_cell("Total Construction Area (Sq.ft.)")]
        + [bold_num(cr(bua.get(s, {}).get("total_constr_sqft", 0))) for s in schemes],
        [body_cell("Number of Parking")]
        + [
            num_cell(str(bua.get(s, {}).get("parking", 90 if s == "33(7)(B)" else 120)))
            for s in schemes
        ],
    ]
    t3 = Table(detail_rows, colWidths=[200, 74, 74, 74, 74])
    ts3 = section_table_style()
    ts3.add("ALIGN", (1, 1), (-1, -1), "RIGHT")
    for r in [7, 8, 11]:
        ts3.add("BACKGROUND", (0, r), (-1, r), NAVY)
        ts3.add("TEXTCOLOR", (0, r), (-1, r), WHITE)
        ts3.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
    t3.setStyle(ts3)
    story.append(t3)
    story.append(PageBreak())


# ── Annexure III — Financial ───────────────────────────────────────────────
def build_annexure_iii(story, data):
    story.append(annexure_banner("ANNEXURE III : FINANCIAL CALCULATION", data.get("ref_no", "")))
    story.append(SP(8))

    fin = data.get("financial", {})
    schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

    def fin_row(label, key, bold=False, subtotal=False, crore=True):
        vals = []
        for s in schemes:
            v = fin.get(s, {}).get(key, 0)
            txt = f"₹{cr(v)}" if v else "—"
            vals.append(bold_num(txt) if (bold or subtotal) else num_cell(txt))
        return [bold_num(label) if bold or subtotal else body_cell(label), *vals]

    def crore_row(label, key):
        vals = []
        for s in schemes:
            v = fin.get(s, {}).get(key, 0)
            if v:
                crore_val = v / 1e7
                txt = f"≈ {crore_val:.2f} Cr"
            else:
                txt = "—"
            vals.append(num_cell(txt))
        return [P(f"<i>{label}</i>", "ReportItalic"), *vals]

    hdr = [hdr_cell("Description")] + [hdr_cell(f"{s}\nAmount (₹)") for s in schemes]
    col_w = [190, 80, 80, 80, 66]

    def build_section(title, rows_data, story):
        sec = Table([[P(f"  {title}", "BodyBold")]], colWidths=[sum(col_w)])
        sec.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), GOLD),
                    ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(sec)
        rows = [hdr, *rows_data]
        t = Table(rows, colWidths=col_w)
        ts = section_table_style()
        ts.add("ALIGN", (1, 1), (-1, -1), "RIGHT")
        t.setStyle(ts)
        story.append(t)
        story.append(SP(6))

    # 1. Construction Cost
    build_section(
        "1.  Construction Cost of the Project",
        [
            fin_row("1a. Total construction (@ ₹4,000/Sq.ft.)", "const_total"),
            fin_row("1b. Cost of parking (60% of construction)", "parking_cost"),
            fin_row("1d. Total construction cost", "const_subtotal", subtotal=True),
            fin_row("1e. 18% GST on construction cost", "gst"),
            fin_row("1f. Total construction cost with GST", "const_with_gst", bold=True),
            crore_row("Say (Crore)", "const_with_gst"),
        ],
        story,
    )

    # 2. FSI/TDR
    build_section(
        "2.  Cost of FSI, TDR Clubbing and Premiums",
        [
            fin_row("2a. Additional FSI on payment of premium", "add_fsi_premium"),
            fin_row("2b. Fungible compensatory area — Residential", "fungible_res"),
            fin_row("2c. Staircase premium", "staircase_prem"),
            fin_row("2d. Open space deficiency premium", "osd_premium"),
            fin_row("2e. Slum TDR", "slum_tdr"),
            fin_row("2f. General TDR", "general_tdr"),
            fin_row("2g. Total — FSI / TDR / Premiums", "fsi_tdr_total", bold=True),
            crore_row("Say (Crore)", "fsi_tdr_total"),
        ],
        story,
    )

    # 3. MCGM
    build_section(
        "3.  Cost of M.C.G.M. Approvals",
        [
            fin_row("3a. Scrutiny / Amended plan fees", "scrutiny"),
            fin_row("3e. Development charges — Residential", "dev_charges"),
            fin_row("3h. Development cess", "dev_cess"),
            fin_row("3j. Land under construction (LUC) charges", "luc"),
            fin_row("3k. CFO scrutiny fees", "cfo"),
            fin_row("3w. Heritage approval & incidental cost", "heritage"),
            fin_row("3y. Incidental, miscellaneous, contingencies", "misc"),
            fin_row("3.  Total MCGM charges", "mcgm_total", bold=True),
            crore_row("Say (Crore)", "mcgm_total"),
        ],
        story,
    )

    # 4. Prof fees
    build_section(
        "4.  Professional Fees (Architect, Consultants @ ₹125/Sq.ft.)",
        [
            fin_row("4. Professional fees", "prof_fees"),
            crore_row("Say (Crore)", "prof_fees"),
        ],
        story,
    )

    story.append(PageBreak())

    story.append(annexure_banner("ANNEXURE III : FINANCIAL (continued)", data.get("ref_no", "")))
    story.append(SP(8))

    # 5. Accommodation
    build_section(
        "5.  Cost for Temporary Alternate Accommodation",
        [
            fin_row("5a-i.  Commercial — 1st 12 months @ ₹3,600/Sq.ft.", "temp_comm_y1"),
            fin_row("5d-i.  Residential — 1st 12 months @ ₹1,800/Sq.ft.", "temp_res_y1"),
            fin_row("5d-ii. Residential — 13–24 months", "temp_res_y2"),
            fin_row("5d-iii.Residential — 25–36 months", "temp_res_y3"),
            fin_row("5g. Total accommodation cost", "temp_total", bold=True),
            crore_row("Say (Crore)", "temp_total"),
        ],
        story,
    )

    # 6. Stamp duty
    build_section(
        "6.  Cost of Stamp Duty & Registration on Agreements",
        [
            fin_row("6a. Stamp duty on development agreement (6%)", "stamp_duty"),
            fin_row("6b. Registration charges & consultants", "stamp_total"),
            crore_row("Say (Crore)", "stamp_total"),
        ],
        story,
    )

    # 7. Total project cost
    build_section(
        "7.  TOTAL COST OF PROJECT",
        [
            fin_row("7. Total cost of project", "project_total", bold=True),
            crore_row("Say (Crore)", "project_total"),
        ],
        story,
    )

    # 8. Corpus
    build_section(
        "8.  Hardship / Corpus Fund",
        [
            fin_row("8. Corpus fund", "corpus"),
            crore_row("Say (Crore)", "corpus"),
        ],
        story,
    )

    # 9. Grand total
    build_section(
        "9.  TOTAL COST OF REDEVELOPMENT PROJECT (7 + 8)",
        [
            fin_row(
                "9. Total cost of redevelopment project",
                "redevelopment_total",
                bold=True,
            ),
            crore_row("Say (Crore)", "redevelopment_total"),
        ],
        story,
    )

    story.append(PageBreak())


# ── Annexure III — B: Additional Area Entitlement ────────────────────────
def build_additional_area(story, data):
    story.append(
        annexure_banner("ADDITIONAL AREA ENTITLEMENT & PROFIT SUMMARY", data.get("ref_no", ""))
    )
    story.append(SP(8))

    ae = data.get("additional_entitlement", {})
    schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

    def ae_row(label, key, fmt="num", bold=False):
        vals = []
        for s in schemes:
            v = ae.get(s, {}).get(key, "—")
            if fmt == "crore" and isinstance(v, (int, float)):
                txt = f"{v:.2f} Cr"
            elif fmt == "pct" and isinstance(v, (int, float)):
                txt = f"{v * 100:.2f}%"
            elif fmt == "sqft" and isinstance(v, (int, float)):
                txt = f"{v:,.2f}"
            elif isinstance(v, (int, float)):
                txt = f"₹{v:,.0f}"
            else:
                txt = str(v)
            vals.append(bold_num(txt) if bold else num_cell(txt))
        return [bold_num(label) if bold else body_cell(label), *vals]

    hdr = [hdr_cell("#")] + [hdr_cell(s) for s in schemes]
    col_w = [190, 80, 80, 80, 66]

    rows = [
        hdr,
        [body_cell("1. Cost of project")]
        + [num_cell(f"{ae.get(s, {}).get('cost_crore', 0):.2f} Cr") for s in schemes],
        [body_cell("2. Total RERA carpet area incl. Fungible (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('rera_total_sqft', 0):,.2f}") for s in schemes],
        [body_cell("3. Existing carpet area (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('existing_sqft', 0):,.2f}") for s in schemes],
        [body_cell("4. Income per Sq.ft. on sale (₹)")]
        + [num_cell(f"₹{ae.get(s, {}).get('sale_rate', 60000):,.0f}") for s in schemes],
        [bold_num("5. Additional RERA area % considered")]
        + [bold_num(f"{ae.get(s, {}).get('add_rera_pct', 0) * 100:.0f}%") for s in schemes],
        [body_cell("6. Additional area for sale (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('add_area_sqft', 0):,.2f}") for s in schemes],
        [bold_num("7. RERA carpet area available for sale (Sq.ft.)")]
        + [bold_num(f"{ae.get(s, {}).get('sale_area_sqft', 0):,.2f}") for s in schemes],
        [body_cell("8. Revenue from project (₹ Crore)")]
        + [num_cell(f"{ae.get(s, {}).get('revenue_crore', 0):.2f} Cr") for s in schemes],
        [body_cell("9. GST for existing members (₹ Crore)")]
        + [num_cell(f"{ae.get(s, {}).get('gst_crore', 0):.2f} Cr") for s in schemes],
        [bold_num("10. Profit (₹ Crore)")]
        + [bold_num(f"{ae.get(s, {}).get('profit_crore', 0):.2f} Cr") for s in schemes],
        [bold_num("11. Profit %")]
        + [bold_num(f"{ae.get(s, {}).get('profit_pct', 0) * 100:.2f}%") for s in schemes],
    ]

    t = Table(rows, colWidths=col_w)
    ts = section_table_style()
    ts.add("ALIGN", (1, 1), (-1, -1), "RIGHT")
    for r in [5, 7, 10, 11]:
        ts.add("BACKGROUND", (0, r), (-1, r), NAVY)
        ts.add("TEXTCOLOR", (0, r), (-1, r), WHITE)
        ts.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
    t.setStyle(ts)
    story.append(t)

    story.append(SP(10))
    story.append(P("<b>Note:</b>", "BodyBold"))
    notes = [
        "Feasibility Study is only based as per data provided by Society — they are incomplete.",
        "As per DP 2034 online assessment there are setbacks shown on both sides of the road — DP Remarks required.",
        "Approved BMC Plans provided are for Building A only — Building B plans required.",
        "There is no setback shown in the Plan provided by society.",
        "Physical Area of Plot in possession is less than P.R. Card — setback appears to have been handed to BMC.",
        "As per Superimpose of D.P. Remark and T.P. Remark, part of Plot is gone under road setback in SVS Road.",
    ]
    for i, n in enumerate(notes, 1):
        story.append(P(f"  {i}. {n}", "ReportItalic"))
        story.append(SP(2))

    story.append(PageBreak())


# ── Summary page ──────────────────────────────────────────────────────────
def build_summary(story, data):
    story.append(annexure_banner("SUMMARY", data.get("ref_no", "")))
    story.append(SP(8))

    ae = data.get("additional_entitlement", {})
    fin = data.get("financial", {})
    bua = data.get("bua", {})
    fsi = data.get("fsi", {})
    schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]

    def v(d, s, k, default="—"):
        val = d.get(s, {}).get(k, default)
        return val if val != 0 else default

    hdr = [hdr_cell("Description")] + [hdr_cell(s) for s in schemes]
    col_w = [200, 74, 74, 74, 74]

    summary_rows = [
        hdr,
        # Existing
        [bold_num("A. EXISTING AREAS")] + [body_cell("")] * 4,
        [body_cell("Area of Commercial (Sq.ft.)")] + [num_cell("5,325.00")] * 4,
        [body_cell("Number of Commercial Members")] + [num_cell("18")] * 4,
        [body_cell("Area of Residences (Sq.ft.)")] + [num_cell("19,100.00")] * 4,
        [body_cell("Number of Flats")] + [num_cell("28")] * 4,
        # FSI
        [bold_num("B. FSI CALCULATION")] + [body_cell("")] * 4,
        [body_cell("Plot area considered (Sq.m.)")] + [num_cell("1,372.56")] * 4,
        [body_cell("Zonal FSI")]
        + [num_cell(str(fsi.get(s, {}).get("zonal_fsi", 1.33))) for s in schemes],
        [body_cell("Total FSI (base)")]
        + [num_cell(str(fsi.get(s, {}).get("total_fsi", "—"))) for s in schemes],
        [body_cell("Fungible 35%")]
        + [num_cell(str(fsi.get(s, {}).get("fungible", "—"))) for s in schemes],
        [bold_num("Total FSI Permissible")]
        + [bold_num(str(fsi.get(s, {}).get("total_fsi_permissible", "—"))) for s in schemes],
        [body_cell("Total Built-Up Area (Sq.ft.)")]
        + [num_cell(cr(bua.get(s, {}).get("total_bua_sqft", ""))) for s in schemes],
        [body_cell("Total RERA Carpet Area (Sq.ft.)")]
        + [num_cell(cr(bua.get(s, {}).get("rera_carpet_sqft", ""))) for s in schemes],
        # Cost
        [bold_num("C. COST OF PROJECT (₹ Crore)")] + [body_cell("")] * 4,
        [body_cell("Total construction (incl. GST)")]
        + [num_cell(f"{fin.get(s, {}).get('const_with_gst', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("FSI / TDR / Premiums")]
        + [num_cell(f"{fin.get(s, {}).get('fsi_tdr_total', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("MCGM approvals")]
        + [num_cell(f"{fin.get(s, {}).get('mcgm_total', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("Professional fees")]
        + [num_cell(f"{fin.get(s, {}).get('prof_fees', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("Temporary accommodation")]
        + [num_cell(f"{fin.get(s, {}).get('temp_total', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("Stamp duty & registration")]
        + [num_cell(f"{fin.get(s, {}).get('stamp_total', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("Total cost of redevelopment project")]
        + [num_cell(f"{fin.get(s, {}).get('redevelopment_total', 0) / 1e7:.2f}") for s in schemes],
        [body_cell("Corpus fund")]
        + [num_cell(f"{fin.get(s, {}).get('corpus', 0) / 1e7:.2f}") for s in schemes],
        [bold_num("Total Cost of Project (Crore)")]
        + [bold_num(f"₹{ae.get(s, {}).get('cost_crore', 0):.2f} Cr") for s in schemes],
        # Entitlement
        [bold_num("D. ADDITIONAL AREA ENTITLEMENT")] + [body_cell("")] * 4,
        [body_cell("Income per Sq.ft. on sale (₹)")]
        + [num_cell(f"₹{ae.get(s, {}).get('sale_rate', 60000):,}") for s in schemes],
        [body_cell("RERA carpet area (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('rera_total_sqft', 0):,.2f}") for s in schemes],
        [body_cell("Existing carpet area (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('existing_sqft', 0):,.2f}") for s in schemes],
        [body_cell("Additional RERA % considered")]
        + [num_cell(f"{ae.get(s, {}).get('add_rera_pct', 0) * 100:.0f}%") for s in schemes],
        [body_cell("Area available for sale (Sq.ft.)")]
        + [num_cell(f"{ae.get(s, {}).get('sale_area_sqft', 0):,.2f}") for s in schemes],
        [body_cell("Revenue from project (₹ Crore)")]
        + [bold_num(f"{ae.get(s, {}).get('revenue_crore', 0):.2f}") for s in schemes],
        [body_cell("GST for existing members (₹ Crore)")]
        + [num_cell(f"{ae.get(s, {}).get('gst_crore', 0):.2f}") for s in schemes],
        [bold_num("Profit (₹ Crore)")]
        + [bold_num(f"{ae.get(s, {}).get('profit_crore', 0):.2f}") for s in schemes],
        [bold_num("Profit %")]
        + [bold_num(f"{ae.get(s, {}).get('profit_pct', 0) * 100:.2f}%") for s in schemes],
    ]

    t = Table(summary_rows, colWidths=col_w)
    ts = section_table_style()
    ts.add("ALIGN", (1, 1), (-1, -1), "RIGHT")
    # Section header rows
    for r in [1, 6, 14, 24]:
        ts.add("BACKGROUND", (0, r), (-1, r), GOLD)
        ts.add("TEXTCOLOR", (0, r), (-1, r), NAVY)
        ts.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
    # Total rows
    for r in [11, 23, 32, 33]:
        ts.add("BACKGROUND", (0, r), (-1, r), NAVY)
        ts.add("TEXTCOLOR", (0, r), (-1, r), WHITE)
        ts.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
    t.setStyle(ts)
    story.append(t)
    story.append(PageBreak())


# ── Conclusion ────────────────────────────────────────────────────────────
def build_conclusion(story, data):
    story.append(sec_heading("Conclusion"))
    story.append(SP(6))
    story.append(
        P(
            "1.  The calculation as considered when the <b>sale area is only RESIDENTIAL.</b>",
            "Body",
        )
    )
    story.append(
        P(
            "2.  The carpet area of existing Residential (Flat) has been considered as per the data provided by society.",
            "Body",
        )
    )
    story.append(P("3.  <b>Benefits for Members as per the attachment.</b>", "Body"))
    story.append(SP(12))

    # AI Analysis if present
    llm = data.get("llm_analysis", "")
    if llm:
        story.append(sec_heading("AI-Generated Feasibility Analysis"))
        story.append(SP(6))
        for line in llm.split("\n"):
            stripped_line = line.strip()
            if not stripped_line:
                story.append(SP(4))
            elif stripped_line.startswith(("━", "─")):
                story.append(HR())
            elif stripped_line.isupper() and len(stripped_line) > 5:
                story.append(P(f"<b>{stripped_line}</b>", "Body"))
            elif stripped_line.startswith(("•", "-")):
                story.append(P(stripped_line, "BulletBody"))
            else:
                story.append(P(stripped_line, "Body"))
            story.append(SP(1))

    story.append(SP(24))
    story.append(HR())
    story.append(
        P(
            "This feasibility study has been prepared by <b>Globera Engineering Consultancy Pvt. Ltd.</b> "
            "All calculations are provisional and tentative, subject to approval of plans for F.S.I./T.D.R. "
            "by M.C.G.M. and other concerned authorities.",
            "Small",
        )
    )


# ── Master builder ────────────────────────────────────────────────────────
def build_feasibility_pdf(data: dict, output_path: str) -> str:
    """Build complete feasibility PDF. Returns output path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        title=f"Feasibility Report — {data.get('society_name', '')}",
        author="Globera Engineering Consultancy Pvt. Ltd.",
        subject="Redevelopment Feasibility Study",
    )

    story = []
    build_cover(story, data)
    build_enclosures(story, data)
    build_narrative(story, data)
    build_dcpr_fsi(story, data)
    build_annexure_i(story, data)
    build_annexure_ii(story, data)
    build_annexure_iii(story, data)
    build_additional_area(story, data)
    build_summary(story, data)
    build_conclusion(story, data)

    doc.build(
        story,
        onFirstPage=lambda c, d: on_page(c, d, data),
        onLaterPages=lambda c, d: on_page(c, d, data),
    )
    return output_path
