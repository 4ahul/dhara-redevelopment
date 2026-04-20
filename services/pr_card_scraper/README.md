# PR Card Scraper Service - Mahabhumi Bhulekh Land Records

Microservice for automated extraction of property records (PR Cards) from Maharashtra's Mahabhumi Bhulekh land records portal.

## Purpose

Scrapes Maharashtra's land records system to retrieve:
- Property Registration (PR) Card details
- Land ownership information
- Survey number / Gut number details
- Village and Taluka information
- Revenue records

## Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT REQUEST                                  |
|              { survey_no, village, taluka, district }                      |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8007)                               |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Startup Resource Pre-loading                          |
|  +-----------------------------------------------------------------------+  |
|  |  ddddocr Model Loading                                               |  |
|  |  - Pre-load on startup for faster first request                      |  |
|  |  - OCR model for CAPTCHA solving                                     |  |
|  +-----------------------------------------------------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                    Web Scraping Pipeline                                     |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Playwright      |  | Selenium        |  | Browser Automation     |  |
|  | (primary)       |  | (fallback)       |  | (headless Chrome)     |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       CAPTCHA Solving Module                                 |
|  +------------------+  +------------------+  +-------------------------+  |
|  | ddddocr OCR    |  | Image Preprocess |  | Tesseract (fallback)   |  |
|  | (primary OCR)  |  | (OpenCV)          |  | (backup)               |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Data Extraction & Parsing                              |
|  +------------------+  +------------------+  +-------------------------+  |
|  | HTML Parsing    |  | Table Extraction |  | Field Normalization    |  |
|  | (BeautifulSoup)|  | (property data)   |  | (standardize formats)  |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                              RESPONSE                                        |
|   { pr_card_data { survey_no, owner, area, land_type, village },          |
|     verification_status, source_url }                                      |
+-----------------------------------------------------------------------------+
```

## Key Components

### 1. Main Router (routers/)
- **/pr-card/search**: Search by survey/village
- **/pr-card/details**: Get full PR card details
- **/pr-card/verify**: Verify ownership

### 2. Web Scrapers (services/)
- **Playwright Scraper**: Primary scraping method
- **Selenium Scraper**: Fallback method
- **Static Scraper**: For cached data

### 3. CAPTCHA Solver (services/captcha_solver.py)
- **ddddocr**: Primary OCR for CAPTCHA
- **OpenCV Preprocessing**: Image enhancement
- **Tesseract**: Backup OCR

### 4. Data Parser (services/data_parser.py)
- **HTML Parsing**: Extract from web pages
- **Table Parsing**: Handle land record tables
- **Field Extraction**: Get specific fields

## Local Development

### Prerequisites
- Python 3.11+
- Playwright browsers installed
- Chrome browser (for Selenium fallback)

### Setup
```bash
cd services/pr_card_scraper
uv venv .venv --python 3.11
uv sync

# Install Playwright browsers
playwright install chromium

# Start service
.venv\Scripts\python.exe main.py
```

### Environment Variables (.env)
```
APP_NAME=PR Card Scraper
APP_VERSION=1.0.0
MAHABHUMI_URL=https://bhulekh.maharashtra.gov.in
CAPTCHA_TIMEOUT=30
SCRAPE_TIMEOUT=60
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /pr-card/search | POST | Search PR cards |
| /pr-card/details | POST | Get full details |
| /pr-card/verify | POST | Verify ownership |
| /health | GET | Health check |

## Query Flow Example

**Input**:
```json
{
  "survey_no": "123",
  "village": "Khar",
  "taluka": "Mumbai Suburban",
  "district": "Mumbai"
}
```

1. **Navigation**: Open Mahabhumi portal
2. **CAPTCHA Solve**: Solve security CAPTCHA
3. **Form Fill**: Enter search parameters
4. **Submit**: Execute search
5. **Extract**: Parse results page

**Output**:
```json
{
  "pr_card_data": {
    "survey_no": "123",
    "owner": "XYZ Cooperative Housing Society",
    "area": "2500 sq meters",
    "land_type": "Urban - Residential",
    "village": "Khar",
    "taluka": "Mumbai Suburban"
  },
  "verification_status": "verified",
  "source_url": "https://bhulekh.maharashtra.gov.in/..."
}
```

## Error Handling

The service handles:
- **CAPTCHA Failures**: Retry with different OCR
- **Session Timeouts**: Re-authenticate
- **Rate Limiting**: Respect portal limits
- **Partial Data**: Return what's available

## Docker

```bash
docker compose up -d pr_card_scraper
```

## Project Structure

```
pr_card_scraper/
├── main.py                 # FastAPI entry point
├── core/                   # Configuration
├── routers/                # API endpoints
├── services/              # Business logic
│   ├── captcha_solver.py   # CAPTCHA solving
│   ├── playwright_scraper.py # Playwright automation
│   ├── selenium_scraper.py  # Selenium fallback
│   └── data_parser.py      # Data extraction
├── schemas/                # Pydantic models
└── utils/                  # Helper functions
```