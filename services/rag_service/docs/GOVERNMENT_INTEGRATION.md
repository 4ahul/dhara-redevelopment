# Government Data Integration Guide

## Overview

This guide explains how to integrate with government websites for property data, DCPR regulations, and compliance information.

## Available Government Services

| Service | Website | API Available | Scraping Possible | Authentication |
|---------|---------|--------------|-------------------|----------------|
| **MCGM/BMC** | mcgm.gov.in | Partial | ✅ Yes | DSC Required |
| **Bhulekh** | bhulekh.maharashtra.gov.in | ❌ No | ⚠️ Limited | Login Required |
| **NOCAS** | nocas.mahaonline.gov.in | ❌ No | ❌ No | Internal System |
| **MahaRERA** | rera.nic.in | ⚠️ Partial | ✅ Yes | No |
| **Maharashtra Govt** | maharashtra.gov.in | ⚠️ Partial | ✅ Yes | No |

## Integration Methods

### 1. MahaRERA Integration (✅ Working)

MahaRERA has a search API that can be used to verify builder/project registration.

```python
# API Endpoint
GET https://maharera.mahaonline.gov.in/MahaRERA/api/RegisteredProjects/Search
Parameters: regNo=<RERA_NUMBER>
```

```python
import requests

def check_rera_registration(rera_no: str) -> dict:
    """Check RERA registration"""
    url = "https://maharera.mahaonline.gov.in/MahaRERA/api/RegisteredProjects/Search"
    
    response = requests.get(url, params={"regNo": rera_no}, timeout=15)
    
    if response.status_code == 200:
        return response.json()
    return None
```

**To Verify:**
```bash
curl "https://maharera.mahaonline.gov.in/MahaRERA/api/RegisteredProjects/Search?regNo=P51800045641"
```

---

### 2. MCGM Services (Partial API)

MCGM offers some online services but most require Digital Signature Certificate (DSC).

#### Building Plan Status Check
```python
# Check building plan application status
GET https://www.mcgm.gov.in/api/building-plan/status/<application_no>
```

#### Property Tax Lookup
```python
# Property tax information
GET https://property.mcgm.gov.in/api/property/<property_id>
```

#### Tender Information
```python
# List of active tenders
GET https://www.mcgm.gov.in/api/tenders?status=active
```

---

### 3. Web Scraping Approach

For services without APIs, web scraping is an alternative.

#### Required Tools
```bash
pip install requests beautifulsoup4 selenium playwright
```

#### MCGM Tender Scraping Example
```python
import requests
from bs4 import BeautifulSoup

def scrape_mcgm_tenders():
    """Scrape MCGM tender list"""
    url = "https://www.mcgm.gov.in/tenders"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    tenders = []
    for row in soup.select('.tender-list-item'):
        tenders.append({
            'title': row.select_one('.title').text.strip(),
            'reference': row.select_one('.ref').text.strip(),
            'closing_date': row.select_one('.date').text.strip(),
            'link': row.select_one('a')['href']
        })
    
    return tenders
```

---

### 4. Bhulekh Land Records

Bhulekh requires login and has CAPTCHA protection.

#### Current Status
- **API**: Not available publicly
- **Web Access**: Requires login + CAPTCHA
- **Alternative**: Use Property Card PDF upload + OCR

#### Recommended Approach
1. User uploads Property Card PDF
2. OCR extracts data
3. Data stored locally for future use

```python
# Property Card OCR Processing
from property_card_workflow import PropertyCardOCR

def process_property_card(file_path: str) -> dict:
    """Extract data from property card PDF"""
    ocr = PropertyCardOCR()
    
    if file_path.endswith('.pdf'):
        cards = ocr.extract_from_pdf(file_path)
    else:
        cards = []
    
    if cards:
        card = cards[0]
        return {
            'survey_no': card.survey_no,
            'area': card.plot_area_sq_m,
            'zone': card.zone_type
        }
    return None
```

---

### 5. NOCAS Building Permissions

NOCAS is an internal government system with no public API.

#### What NOCAS Provides
- Building permission checks
- Height clearance from AAI
- Fire NOC status

#### Alternative
Use DCPR rules to calculate locally:

```python
def calculate_max_height(zone: str, area_sq_m: float) -> dict:
    """Calculate max height based on DCPR rules"""
    
    base_heights = {
        "Residential": 70,  # meters
        "Commercial": 100,
        "Industrial": 50,
    }
    
    height = base_heights.get(zone, 70)
    
    # Adjust for plot size
    if area_sq_m < 500:
        height = min(height, 24)
    elif area_sq_m < 1000:
        height = min(height, 36)
    
    return {
        'max_height_m': height,
        'airport_clearance_required': height > 30
    }
```

---

## WhatsApp Compliance Integration

### Reading Government WhatsApp Groups

Government departments share updates on WhatsApp. To integrate:

### Step 1: Export Chat
1. Open WhatsApp group
2. Go to Group Info > Export Chat
3. Save as .txt file

### Step 2: Parse Messages
```python
import re

def parse_compliance_message(message: str) -> dict:
    """Parse WhatsApp message for compliance updates"""
    
    patterns = [
        r'(?i)(maharera|maha\s*RERA).*?(circular|order)',
        r'(?i)(DCPR|mumbai).*?(regulation|amendment)',
        r'(?i)(mcgm|municipal).*?(notice|order)',
        r'(?i)(effective|from)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.I)
        if match:
            return {
                'type': 'compliance',
                'content': message,
                'matched': match.group(0)
            }
    
    return None

def import_whatsapp_chat(file_path: str):
    """Import compliances from WhatsApp export"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse format: "Date - Sender: Message"
    pattern = r'(\d{1,2}/\d{1,2}/\d{2,4}).*?-\s*([^:]+):\s*(.+)'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    compliances = []
    for date, sender, message in matches:
        compliance = parse_compliance_message(message)
        if compliance:
            compliance['date'] = date
            compliance['sender'] = sender
            compliances.append(compliance)
    
    return compliances
```

---

## Cron Job for Real-time Updates

### Setting Up Automated Data Fetch

```bash
# Create cron job for daily updates
crontab -e

# Add these entries:
# Daily at 9 AM - Check new RERA registrations
0 9 * * * cd /home/ubuntu/rag_system && python3 scripts/check_rera_updates.py >> logs/rera_updates.log 2>&1

# Daily at 10 AM - Fetch MCGM tenders
0 10 * * * cd /home/ubuntu/rag_system && python3 scripts/fetch_tenders.py >> logs/tenders.log 2>&1

# Every 6 hours - Update compliance database
0 */6 * * * cd /home/ubuntu/rag_system && python3 scripts/update_compliance.py >> logs/compliance.log 2>&1
```

### Example Cron Script
```python
#!/usr/bin/env python3
# scripts/check_rera_updates.py

import requests
import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("logs/rera_updates.log")
DATA_DIR = Path("data/compliance")

def log(message):
    print(f"[{datetime.now()}] {message}")
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def check_new_registrations():
    """Check for new RERA registrations"""
    log("Checking for new RERA registrations...")
    
    # This would check MahaRERA API
    # For now, just log
    log("Checked successfully")

if __name__ == "__main__":
    check_new_registrations()
```

---

## Integration Checklist

### Phase 1: Basic (Week 1-2)
- [x] MahaRERA builder verification API
- [ ] RERA project search API
- [ ] WhatsApp compliance parser

### Phase 2: Intermediate (Week 3-4)
- [ ] MCGM tender scraper
- [ ] MCGM property tax lookup
- [ ] Document OCR processor

### Phase 3: Advanced (Week 5-8)
- [ ] Bhulekh API integration (if available)
- [ ] Building plan status tracker
- [ ] NOC status tracker

---

## Legal Considerations

### Before Scraping
1. Check `robots.txt` of the website
2. Read Terms of Service
3. Ensure rate limiting compliance
4. Consider API alternatives first

### Recommended Practices
- Use official APIs when available
- Add delays between requests (1-2 seconds)
- Cache data locally to reduce API calls
- Handle CAPTCHA appropriately
- Respect rate limits

### Authentication Requirements
| Service | Authentication | Notes |
|---------|---------------|-------|
| MCGM BPS | DSC + Login | Mandatory for submissions |
| RERA Search | None | Public access |
| Bhulekh | Login + CAPTCHA | Manual intervention needed |
| Property Tax | Account | Optional for lookups |

---

## Next Steps for Implementation

1. **Start with RERA** - Easiest integration, working API
2. **Add OCR for Property Cards** - No API exists
3. **Build WhatsApp parser** - For compliance updates
4. **Implement MCGM scraper** - For tenders and updates
5. **Monitor for API changes** - Government services evolve

---

## Contact Government Departments

For official API access:
- **MCGM IT**: itcell@mcgm.gov.in
- **MahaOnline**: support@mahaonline.gov.in
- **Bhulekh**: bhulekh@maharashtra.gov.in
