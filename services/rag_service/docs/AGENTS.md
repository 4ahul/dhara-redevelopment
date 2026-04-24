# DCPR RAG + Property Card Analysis System

## Overview

Production-ready RAG system for DCPR 2034 regulations with property card analysis and LandWise-style report generation.

### Features

- **DCPR 2034 Knowledge Base**: 939 chunks indexed for semantic search
- **Milvus Vector Database**: High-performance similarity search
- **Property Card Analysis**: OCR + structured data extraction
- **Report Generation**: LandWise-style financial reports (PDF + text)
- **Multi-Scheme Support**: 33(20B), 33(11), 33(7B), 30(A)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   CLI / API                          │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────────────────────┐│
│  │ RAG Query    │  │ Property Card Workflow       ││
│  │ (DCPR)       │  │ - OCR/EasyOCR                ││
│  └──────────────┘  │ - DCPR Calculator            ││
│                      │ - Report Generator          ││
│                      └──────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐│
│  │ Milvus Vector Store (939 chunks)                 ││
│  │ nomic-embed-text embeddings                      ││
│  └──────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  Ollama (qwen2.5:7b, nomic-embed-text)             │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start System

```bash
cd /home/ubuntu/rag_system
bash start.sh
```

### 2. Query DCPR Regulations

```bash
# Single query
python3 cli.py query "What is the FSI for residential buildings?"

# Interactive mode
python3 cli.py interactive
```

### 3. Analyze Property

```bash
# Analyze a property
python3 cli.py analyze \
  --survey-no "123/P" \
  --area 2200 \
  --road-width 12 \
  --scheme "33(7B)" \
  --residential-rate 50000 \
  --output reports/
```

### 4. Compare Schemes

```bash
python3 cli.py compare --area 2200
```

### 5. Parse Existing LandWise Report

```python
from property_card_workflow import LandWiseReportParser

# Parse financial summary
analysis = LandWiseReportParser.parse_financial_summary("report.pdf")
print(f"Revenue: ₹{analysis.total_revenue_cr} Cr")
print(f"Profit: ₹{analysis.net_profit_cr} Cr")
```

## CLI Commands

### query
Query DCPR 2034 regulations using semantic search.

```bash
python3 cli.py query "FSI calculation for commercial" --k 5
```

### analyze
Analyze a property and generate reports.

```bash
python3 cli.py analyze \
  --survey-no "CTS 123" \
  --area 2200 \
  --road-width 12 \
  --zone Residential \
  --scheme "33(7B)" \
  --output reports/
```

Options:
- `--survey-no`: Survey/Plot number
- `--area`: Plot area in sq.m
- `--road-width`: Road width in meters (default: 9)
- `--zone`: Zone type (Residential/Commercial/Industrial)
- `--scheme`: DCPR scheme (33(20B)/33(11)/33(7B)/30(A))
- `--affordable-housing`: Affordable housing percentage for 33(7B) incentive (default: 70)
- `--residential-rate`: Rate per sq.ft for residential (default: 50000)

### compare
Compare different DCPR schemes for a given plot area.

```bash
python3 cli.py compare --area 2200 --schemes 33(20B) 33(11) 33(7B) 30(A)
```

Options:
- `--area`: Plot area in sq.m
- `--schemes`: List of schemes to compare
- `--affordable-housing`: Affordable housing percentage for 33(7B) incentive (default: 70)

### scan
Scan property card from PDF/image using OCR.

```bash
python3 cli.py scan --input property_card.pdf --output reports/
```

### stats
Show system statistics.

```bash
python3 cli.py stats
```

### index
Index DCPR document to Milvus.

```bash
# Index DCPR document
python3 cli.py index --pdf "/path/to/dcpr.pdf"

# Rebuild index
python3 cli.py index --rebuild
```

## DCPR Schemes

| Scheme | Basic FSI | Incentive | Max FSI | Premium |
|--------|----------|----------|---------|---------|
| 33(20B) | 2.5 | 0.0 | 4.0 | 0.5 |
| 33(11) | 1.0 | 0.0 | 4.0 | 0.5 |
| 33(7B) | 0.5 | 0.15 | 4.0 | 0.5 |
| 30(A) | 2.5 | 0.0 | 4.0 | 0.5 |

## Property Card Workflow

### PropertyCard Data Structure

```python
@dataclass
class PropertyCard:
    survey_no: str
    plot_area_sq_m: float
    plot_area_sq_ft: float
    road_width_m: float
    zone_type: str  # Residential/Commercial/Industrial
    village: str
    taluka: str
    district: str
```

### ProjectAnalysis Data Structure

```python
@dataclass
class ProjectAnalysis:
    project_name: str
    property_card: PropertyCard
    selected_scheme: str
    revenue: RevenueBreakdown
    cost_breakdown: CostBreakdown
    total_revenue_cr: float
    total_cost_cr: float
    gross_profit_cr: float
    net_profit_cr: float
    gross_margin_pct: float
    net_margin_pct: float
```

## Generated Reports

### Financial Summary (PDF)

- Area Summary (RERA Carpet)
- Revenue Summary
- Cost Summary
- Profitability Analysis

### Scheme Comparison

- FSI breakdown by scheme
- Plot area calculations
- Premium FSI options

### Approval Cost Summary

- Scrutiny fees
- Deposits
- Premium charges
- Development charges

## Docker Services

The system uses docker-compose with:

- **etcd**: Metadata storage
- **minio**: Object storage  
- **milvus**: Vector database (port 19530)

### Start/Stop

```bash
# Start
cd /home/ubuntu/rag_system
sudo docker-compose -f docker-compose.milvus.yml up -d

# Stop
sudo docker-compose -f docker-compose.milvus.yml down

# Logs
sudo docker-compose -f docker-compose.milvus.yml logs -f
```

## File Structure

```
rag_system/
├── cli.py                  # Unified CLI
├── rag.py                 # RAG core (Milvus integration)
├── property_card_workflow.py  # Property analysis + reports
├── docker-compose.milvus.yml  # Milvus stack
├── start.sh               # Startup script
├── data/
│   ├── vectors/           # Cached embeddings
│   └── feedback.json      # Expert feedback
└── reports/              # Generated reports
```

## Requirements

- Python 3.12+
- Ollama (qwen2.5:7b, nomic-embed-text)
- Docker + docker-compose
- Milvus 2.6
- EasyOCR (optional, for image scanning)
- reportlab (PDF generation)

## Troubleshooting

### Milvus not starting

```bash
# Check Docker
sudo docker ps -a

# View logs
sudo docker logs milvus

# Restart
sudo docker-compose -f docker-compose.milvus.yml restart
```

### Slow queries

- Increase Milvus index nlist
- Use GPU for embeddings
- Reduce chunk size

### OCR not working

```bash
# Install EasyOCR
pip install easyocr

# Use GPU for faster OCR
reader = easyocr.Reader(['en'], gpu=True)
```

## Examples

### Full Property Analysis

```python
from property_card_workflow import PropertyCardWorkflow, PropertyCard, RevenueBreakdown

# Create property
card = PropertyCard(
    survey_no="123/P",
    plot_area_sq_m=2200,
    road_width_m=12,
    zone_type="Residential"
)

# Define revenue model
revenue = RevenueBreakdown(
    residential_area_sqft=30000,
    residential_rate_per_sqft=50000,
    parking_slots=50
)

# Analyze
workflow = PropertyCardWorkflow()
analysis = workflow.analyze_from_card(card, schemes=["33(7B)"], revenue=revenue)

# Generate PDF report
workflow.generator.export_to_pdf(analysis, "report.pdf", "financial")
```

### Parse Existing LandWise Report

```python
from property_card_workflow import LandWiseReportParser

# Parse financial summary
analysis = LandWiseReportParser.parse_financial_summary("financial_summary.pdf")

# Parse scheme comparison
data = LandWiseReportParser.parse_scheme_comparison("scheme_comparison.pdf")
```

## License

Internal use only - Property of Archonet
