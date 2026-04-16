# Dhara RAG System

Production-ready RAG system for PMC (Project Management Consultant) real estate redevelopment operations in Pune, Maharashtra. Combines DCPR 2034 knowledge base with property card analysis and government integration.

## Features

- **DCPR 2034 Knowledge Base**: Semantic search on Development Control and Promotion Regulations 2034
- **Milvus Vector Database**: High-performance similarity search with 939 indexed chunks
- **Property Card Analysis**: OCR-based extraction and structured data analysis
- **PMC Workflow Engine**: End-to-end project management from feasibility to conveyance
- **Government Integrations**: BMC, RERA, Bhulekh, NOCAS data aggregation
- **WhatsApp Compliance Parser**: Automated compliance monitoring from government updates
- **Multi-Scheme Support**: 33(20B), 33(11), 33(7B), 30(A) DCPR schemes
- **Report Generation**: LandWise-style financial reports (PDF + text)

## Architecture

```
+-------------------+     +-------------------+     +-------------------+
|                   |     |                   |     |                   |
|   CLI (cli.py)    |<--->|  FastAPI (api.py) |<--->|   Milvus (19530)  |
|                   |     |                   |     |                   |
+-------------------+     +-------------------+     +-------------------+
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
+-------------------+     +-------------------+     +-------------------+
|  Property Card    |     |   PMC Workflow    |     |  Government Data  |
|  Workflow         |     |   Engine          |     |  Integrations     |
+-------------------+     +-------------------+     +-------------------+
                                   |
+-------------------+     +-------------------+     +-------------------+
|  OCR (EasyOCR)    |     |   RERA/RAG        |     |  WhatsApp Parser  |
+-------------------+     +-------------------+     +-------------------+
```

## Requirements

- Python 3.12+
- Docker + docker-compose
- Milvus 2.6
- OpenAI API key (gpt-4o-mini)
- Ollama (optional, for local embeddings)

## Installation

### 1. Clone and Setup

```bash
git clone https://github.com/Himan-D/dhara-rag.git
cd dhara-rag
pip install -r requirements.txt
```

### 2. Start Milvus

```bash
sudo docker-compose -f docker-compose.milvus.yml up -d
```

### 3. Configure Environment

Create `.env` file:

```bash
OPENAI_API_KEY=sk-...
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### 4. Index DCPR Document

```bash
python3 cli.py index --pdf "/path/to/dcpr.pdf"
```

## CLI Usage

### Query DCPR Regulations

```bash
python3 cli.py query "What is the FSI for residential buildings?" --k 5
```

### Analyze Property

```bash
python3 cli.py analyze \
  --survey-no "123/P" \
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

### Compare Schemes

```bash
python3 cli.py compare --area 2200 --schemes 33(20B) 33(11) 33(7B) 30(A)
```

### Scan Property Card

```bash
python3 cli.py scan --input property_card.pdf --output reports/
```

### System Statistics

```bash
python3 cli.py stats
```

### Interactive Mode

```bash
python3 cli.py interactive
```

## API Usage

### Start Server

```bash
python3 api.py
```

API runs on http://localhost:8000 with Swagger docs at http://localhost:8000/docs

### Endpoints

#### Project Management

- `POST /api/projects` - Create new project
- `GET /api/projects` - List all projects
- `GET /api/projects/{id}` - Get project details
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

#### Feasibility Reports

- `POST /api/feasibility` - Generate feasibility report
- `GET /api/feasibility/{id}` - Get feasibility report

#### Compliance

- `POST /api/compliance/whatsapp` - Parse WhatsApp compliance updates
- `GET /api/compliance/status` - Get compliance status
- `POST /api/compliance/rera-check` - Check RERA updates

#### OCR

- `POST /api/ocr/property-card` - Extract property card data
- `POST /api/ocr/7-12` - Extract 7-12 extract data

### Example Request

```bash
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Society Redevelopment",
    "society_name": "Test CHS",
    "plot_area_sqm": 2200,
    "road_width_m": 12,
    "scheme": "33(7B)"
  }'
```

## DCPR Schemes

| Scheme   | Basic FSI | Incentive FSI | Max FSI | Premium FSI |
|----------|-----------|---------------|---------|-------------|
| 33(20B)  | 2.5       | 0.0           | 4.0     | 0.5         |
| 33(11)   | 1.0       | 0.0           | 4.0     | 0.5         |
| 33(7B)   | 0.5       | 0.15          | 4.0     | 0.5         |
| 30(A)    | 2.5       | 0.0           | 4.0     | 0.5         |

### 33(7B) Affordable Housing Incentive

Projects under 33(7B) can receive additional FSI incentive based on affordable housing percentage:

- 70% affordable housing: 0.15 extra FSI
- 35% affordable housing: 0.10 extra FSI
- 20% affordable housing: 0.05 extra FSI

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

## Government Integrations

### RERA Integration

Verifies project registration and tracks updates:

```python
from integrations.rera_integration import RERAIntegration

rera = RERAIntegration()
status = rera.check_registration("P52100000000")
```

### WhatsApp Compliance Parser

Parses exported WhatsApp chats for compliance updates:

```python
from integrations.whatsapp_integration import WhatsAppComplianceParser

parser = WhatsAppComplianceParser()
compliance_items = parser.parse_chat_export("chat_export.txt")
```

### BMC Integration

Aggregates building and development data:

```python
from data_sources import GovernmentDataAggregator

aggregator = GovernmentDataAggregator()
data = aggregator.get_property_data(survey_no="123/P", village="Viman Nagar")
```

## Cron Automation

### Setup Cron Jobs

```bash
bash setup_cron.sh
```

### Available Cron Scripts

- `scripts/check_rera_updates.py` - Daily RERA registration checks
- `scripts/check_whatsapp_compliance.py` - Hourly compliance monitoring
- `scripts/process_uploads.py` - Document processing queue

## File Structure

```
dhara-rag/
├── cli.py                      # Unified CLI
├── api.py                      # FastAPI backend
├── rag.py                      # RAG core with Milvus
├── pmc_workflow.py             # PMC workflow engine
├── property_card_workflow.py   # Property analysis + reports
├── data_sources.py             # Government data aggregator
├── gov_integrations.py         # BMC, Bhulekh, NOCAS
├── gov_data_integration.py     # Hybrid integration
├── ocr_api.py                  # OCR upload API
├── docker-compose.milvus.yml   # Milvus stack
├── setup_cron.sh               # Cron installation
├── integrations/
│   ├── rera_integration.py     # RERA verification
│   └── whatsapp_integration.py  # WhatsApp compliance
├── scripts/
│   ├── check_rera_updates.py
│   ├── check_whatsapp_compliance.py
│   └── process_uploads.py
├── docs/
│   ├── GOVERNMENT_INTEGRATION.md
│   └── INTEGRATION_IMPLEMENTATION.md
├── data/
│   ├── vectors/                 # Cached embeddings
│   ├── workflows/              # Project workflows
│   ├── projects/               # Saved projects
│   ├── uploads/                # Uploaded documents
│   └── compliance/              # WhatsApp compliance DB
└── reports/                    # Generated reports
```

## Generated Reports

### Financial Summary

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

## Troubleshooting

### Milvus not starting

```bash
sudo docker ps -a
sudo docker logs milvus
sudo docker-compose -f docker-compose.milvus.yml restart
```

### Slow queries

- Increase Milvus index nlist
- Use GPU for embeddings
- Reduce chunk size

### OCR not working

```bash
pip install easyocr
python3 -c "import easyocr; print('OK')"
```

## Development

### Run Tests

```bash
python3 -m pytest tests/
```

### Code Style

```bash
ruff check .
```

## License

Internal use only - Property of Archonet

## Support

For issues and feature requests, please open a GitHub issue.
