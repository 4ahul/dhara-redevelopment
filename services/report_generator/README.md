# Report Generator Service - Excel and PDF Feasibility Reports

Microservice for generating professional feasibility reports in Excel and PDF format for redevelopment proposals, combining data from all other services.

## Purpose

Generates comprehensive feasibility reports for redevelopment projects:
- Excel reports with yellow cell inputs for user modification
- PDF reports with formatted summary
- Scheme-specific templates (33(7)(B), 33(7)(A), EWS, etc.)
- Financial calculations and summaries

## Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT REQUEST                                  |
|    { scheme, redevelopment_type, society_data, dp_report, financials }     |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8005)                               |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Template Selection Engine                             |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Scheme Detection|  | Template Lookup  |  | Field Mapping          |  |
|  | (33(7)(B), etc.)|  | (Excel template) |  | (data -> yellow cells) |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Data Processing Pipeline                              |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Data Normalizer |  | Cell Mapper      |  | Validation             |  |
|  | (unify formats) |  | (map to cells)   |  | (schema validation)   |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                      Report Generation Engines                              |
|  +---------------------------+  +----------------------------------------+  |
|  | Excel Builder            |  | PDF Builder                            |  |
|  | (openpyxl + templates)   |  | (reportlab + data)                    |  |
|  +---------------------------+  +----------------------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                              OUTPUT                                          |
|   { excel_file, pdf_file, validation_results, summary }                   |
+-----------------------------------------------------------------------------+
```

## Key Components

### 1. Report Router (routers/report_router.py)
- **/generate**: Generate full report (Excel + PDF)
- **/template/fields**: Get template field schema
- **/template/apply**: Apply data to template
- **/validate**: Validate input data

### 2. Template Service (services/template_service.py)
- **Template Loading**: Load Excel templates by scheme
- **Field Schema**: Expose editable fields
- **Data Application**: Fill yellow cells

### 3. Cell Mapper (services/cell_mapper.py)
- **Field Mapping**: Map input data to cell positions
- **Formula Preservation**: Keep existing formulas
- **Validation**: Verify required fields

### 4. Excel Builder (services/excel_builder.py)
- **Template Fill**: Fill template with data
- **Formatting**: Maintain styling
- **Cell Locking**: Protect formula cells

### 5. PDF Builder (services/pdf_builder.py)
- **Summary Generation**: Create text summary
- **Formatting**: Professional layout
- **Charts**: Add charts if needed

## Local Development

### Prerequisites
- Python 3.11+
- Microsoft Excel (for template editing)

### Setup
```bash
cd services/report_generator
uv venv .venv --python 3.11
uv sync

# Start service
.venv\Scripts\python.exe main.py
```

### Environment Variables (.env)
```
APP_NAME=Report Generator Service
APP_VERSION=1.0.0
OUTPUT_DIR=./output
TEMPLATE_DIR=./templates
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /generate | POST | Generate full report |
| /template/fields | GET | Get template fields |
| /template/apply | POST | Apply data to template |
| /validate | POST | Validate input data |
| /health | GET | Health check |

## Query Flow Example

**Input**:
```json
{
  "scheme": "33(7)(B)",
  "redevelopment_type": "SOCIETY",
  "society_data": {
    "name": "Sunrise CHS",
    "plot_area": 2500,
    "total_members": 24
  },
  "dp_report": {
    "zone": "Residential",
    "fsi": 2.0,
    "max_height": 35
  },
  "financials": {
    "construction_cost": 15000000,
    "saleable_area": 4500
  }
}
```

1. **Template Selection**: Select 33(7)(B) template
2. **Field Mapping**: Map data to yellow cells
3. **Validation**: Check required fields
4. **Excel Generation**: Create .xlsx file
5. **PDF Generation**: Create summary PDF

**Output**:
```json
{
  "excel_file": "Feasibility_33(7)(B)_SOCIETY_Sunrise_CHS.xlsx",
  "pdf_file": "Feasibility_33(7)(B)_Sunrise_CHS.pdf",
  "validation_results": {"valid": true, "warnings": []},
  "summary": {
    "total FSI": 2.0,
    "construction_cost": 15000000,
    "saleable_area": 4500
  }
}
```

## Excel Template Format

The service uses Excel templates with:
- **Yellow cells**: User-editable inputs
- **White cells**: Calculated outputs (formulas)
- **Protected sheets**: Formula protection

## Docker

```bash
docker compose up -d report_generator
```

## Project Structure

```
report_generator/
├── main.py                 # FastAPI entry point
├── core/                   # Configuration
│   └── config.py          # Settings and paths
├── routers/                # API endpoints
│   └── report_router.py   # Report endpoints
├── services/              # Business logic
│   ├── template_service.py   # Template management
│   ├── cell_mapper.py        # Cell mapping
│   ├── excel_builder.py      # Excel generation
│   ├── excel_to_pdf.py       # PDF from Excel
│   ├── pdf_builder.py        # PDF generation
│   └── data_normalizer.py    # Data processing
├── schemas/                # Pydantic models
│   └── report.py           # Request/response schemas
├── templates/              # Excel templates
└── output/                # Generated reports
```