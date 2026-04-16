# Government Integration - Exact Implementation Process

## Summary: What Method to Use

| Data Source | Best Method | Difficulty | Time |
|------------|------------|-----------|------|
| **RERA Registration** | Direct HTTP Request | Easy | 1 day |
| **MCGM Tenders** | Web Scraping (Requests + BeautifulSoup) | Medium | 2 days |
| **MCGM Property Tax** | Web Scraping | Medium | 2 days |
| **Property Card (7/12)** | OCR Upload | Easy | 1 day |
| **Bhulekh Land Records** | Upload + Manual | N/A | N/A |
| **WhatsApp Compliance** | File Import + Parser | Easy | 1 day |
| **Building Plans** | Not Possible | N/A | N/A |

## DON'T USE SELENIUM UNLESS NECESSARY

Selenium is heavy and slow. Use it only when:
- Website uses JavaScript heavily
- Login with CAPTCHA required
- No API available

**Prefer**: `requests` → `BeautifulSoup` → `Selenium` (last resort)

---

## Implementation 1: RERA API (Recommended - Start Here)

### Exact Code

```python
# File: integrations/rera_integration.py

import requests
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

BASE_URL = "https://maharera.mahaonline.gov.in/MahaRERA/api"

@dataclass
class RERAProject:
    registration_no: str
    project_name: str
    promoter_name: str
    gantt_chart_available: bool
    rera_link: str
    valid_upto: str
    total_units: int

class RERAIntegration:
    """MahaRERA API Integration"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json',
            'Referer': 'https://maharera.mahaonline.gov.in'
        })
    
    def search_by_registration(self, reg_no: str) -> dict:
        """Search by RERA registration number"""
        try:
            url = f"{BASE_URL}/RegisteredProjects/Search"
            params = {"regNo": reg_no}
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_project_details(self, project_id: str) -> dict:
        """Get detailed project information"""
        try:
            url = f"{BASE_URL}/ProjectDetails/{project_id}"
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def check_builder(self, builder_name: str) -> list:
        """Search builder by name"""
        try:
            url = f"{BASE_URL}/Promoter/Search"
            params = {"name": builder_name}
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json().get("results", [])
            
            return []
        except Exception as e:
            print(f"Error: {e}")
            return []

# Usage
if __name__ == "__main__":
    rera = RERAIntegration()
    
    # Check specific registration
    result = rera.search_by_registration("P51800045641")
    print(json.dumps(result, indent=2))
```

### Test Command
```bash
python integrations/rera_integration.py
```

---

## Implementation 2: MCGM Tender Scraper

### Exact Code

```python
# File: integrations/mcgm_tenders.py

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path

class MCGMTenderScraper:
    """Scrape MCGM tender information"""
    
    BASE_URL = "https://www.mcgm.gov.in"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        })
    
    def get_active_tenders(self) -> list:
        """Get list of active tenders"""
        try:
            url = f"{self.BASE_URL}/tenders"
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tenders = []
            
            # Find tender table or list
            tender_rows = soup.select('.tender-item, .tender-list tr, table.tenders tr')
            
            for row in tender_rows[1:]:  # Skip header
                cols = row.select('td')
                
                if len(cols) >= 4:
                    tender = {
                        'reference_no': cols[0].get_text(strip=True),
                        'subject': cols[1].get_text(strip=True),
                        'publish_date': cols[2].get_text(strip=True),
                        'closing_date': cols[3].get_text(strip=True),
                        'department': cols[4].get_text(strip=True) if len(cols) > 4 else '',
                        'link': self.BASE_URL + cols[1].select_one('a')['href'] if cols[1].select_one('a') else ''
                    }
                    tenders.append(tender)
            
            return tenders
            
        except Exception as e:
            print(f"Error fetching tenders: {e}")
            return []
    
    def get_tender_details(self, tender_link: str) -> dict:
        """Get detailed tender information"""
        try:
            response = self.session.get(tender_link, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            details = {}
            
            # Extract common fields
            for field in soup.select('.field, .detail-row'):
                label = field.select_one('label, .label')
                value = field.select_one('span, .value, td:last-child')
                
                if label and value:
                    details[label.get_text(strip=True)] = value.get_text(strip=True)
            
            return details
            
        except Exception as e:
            print(f"Error: {e}")
            return {}

# Usage
if __name__ == "__main__":
    scraper = MCGMTenderScraper()
    
    print("Fetching active tenders...")
    tenders = scraper.get_active_tenders()
    
    print(f"\nFound {len(tenders)} tenders:")
    for t in tenders[:5]:
        print(f"  - {t['reference_no']}: {t['subject'][:50]}...")
```

### Test Command
```bash
python integrations/mcgm_tenders.py
```

---

## Implementation 3: WhatsApp Compliance Parser

### Exact Code

```python
# File: integrations/whatsapp_compliance.py

import re
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class ComplianceUpdate:
    title: str
    description: str
    source: str
    date: str
    category: str
    url: str = ""
    raw_text: str = ""

class WhatsAppComplianceParser:
    """Parse WhatsApp exports for compliance updates"""
    
    # Patterns for government compliance notifications
    PATTERNS = [
        # MahaRERA
        (r'(?i)(maharera|maha\s*rera).*?(circular|order|notification)\s*[:\-]?\s*(.+)', 'rera'),
        
        # DCPR/Regulations
        (r'(?i)(DCPR|DCR|mumbai).*?(regulation|amendment|rule)\s*[:\-]?\s*(.+)', 'dcpr'),
        
        # MCGM
        (r'(?i)(mcgm|municipal).*?(notice|order|amendment)\s*[:\-]?\s*(.+)', 'mcgm'),
        
        # Government
        (r'(?i)(govt|government|maharashtra).*?(notification|order)\s*[:\-]?\s*(.+)', 'government'),
        
        # Effective date
        (r'(?i)(effective|from)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*[:\-]?\s*(.+)', 'effective_date'),
        
        # FSI changes
        (r'(?i)(FSI|FAR|building\s*permission).*?(changed|amended|new)\s*[:\-]?\s*(.+)', 'fsi'),
        
        # Fire safety
        (r'(?i)fire.*?(safety|noc|规则).*?(new|amended)\s*[:\-]?\s*(.+)', 'fire'),
    ]
    
    def __init__(self):
        self.data_dir = Path("data/compliance")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def parse_file(self, file_path: str) -> list:
        """Parse WhatsApp chat export file"""
        compliances = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern: Date, Time - Sender: Message
        # OR: Date/Time - Sender: Message
        
        pattern = r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s*(\d{1,2}:\d{2})?\s*-\s*([^:]+):\s*(.+?)(?=\n\d{1,2}[\/\-]|$)'
        
        matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
        
        for date, time, sender, message in matches:
            compliance = self._parse_message(message.strip(), sender.strip(), date)
            
            if compliance:
                compliances.append(compliance)
        
        return compliances
    
    def _parse_message(self, message: str, sender: str, date: str) -> ComplianceUpdate:
        """Parse individual message"""
        
        for pattern, category in self.PATTERNS:
            match = re.search(pattern, message, re.I)
            
            if match:
                groups = match.groups()
                
                # Extract title from groups
                title = ""
                for g in reversed(groups):
                    if g and len(g.strip()) > 5:
                        title = g.strip()[:100]
                        break
                
                return ComplianceUpdate(
                    title=title,
                    description=message.strip(),
                    source=f"WhatsApp - {sender}",
                    date=date,
                    category=category,
                    raw_text=message
                )
        
        return None
    
    def save_compliances(self, compliances: list):
        """Save compliances to file"""
        output_file = self.data_dir / f"whatsapp_compliances_{datetime.now().strftime('%Y%m%d')}.json"
        
        data = [asdict(c) for c in compliances]
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(compliances)} compliances to {output_file}")

# Usage
if __name__ == "__main__":
    parser = WhatsAppComplianceParser()
    
    # Parse WhatsApp export
    compliances = parser.parse_file("data/whatsapp_export.txt")
    
    print(f"Found {len(compliances)} compliance updates:")
    for c in compliances:
        print(f"  [{c.category}] {c.title[:60]}")
    
    if compliances:
        parser.save_compliances(compliances)
```

### WhatsApp Export Format

To export from WhatsApp:
1. Open group → Group Info
2. Scroll up → Export Chat
3. Save without media

### Test Command
```bash
# First, create sample WhatsApp export file
echo "1/15/2024, 9:30 AM - Government Updates: MahaRERA circular regarding deemed conveyance process - effective from 1/2/2024" > data/sample_whatsapp.txt
echo "1/16/2024, 10:00 AM - MCGM Dept: New DCPR regulation for FSI calculation in residential zones" >> data/sample_whatsapp.txt

python integrations/whatsapp_compliance.py
```

---

## Implementation 4: Property Card OCR

### Exact Code

```python
# File: integrations/property_card_ocr.py

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ExtractedProperty:
    survey_no: str = ""
    plot_area_sq_m: float = 0.0
    plot_area_sq_ft: float = 0.0
    road_width_m: float = 0.0
    zone_type: str = ""
    village: str = ""
    taluka: str = ""
    district: str = ""
    tenure: str = ""
    owners: List[str] = None

class PropertyCardOCR:
    """OCR for Property Cards and 7-12 extracts"""
    
    def __init__(self):
        self.easyocr_available = False
        try:
            import easyocr
            self.reader = easyocr.Reader(['en', 'mr'])  # English + Marathi
            self.easyocr_available = True
            print("✓ EasyOCR initialized (with Marathi support)")
        except ImportError:
            print("⚠ EasyOCR not available, using basic extraction")
    
    def extract_from_image(self, image_path: str) -> ExtractedProperty:
        """Extract from image file"""
        if not self.easyocr_available:
            raise RuntimeError("EasyOCR not installed")
        
        result = self.reader.readtext(image_path, detail=0)
        text = "\n".join(result)
        
        return self._parse_text(text)
    
    def extract_from_pdf(self, pdf_path: str) -> List[ExtractedProperty]:
        """Extract from PDF"""
        from pypdf import PdfReader
        
        properties = []
        reader = PdfReader(pdf_path)
        
        for page in reader.pages:
            text = page.extract_text()
            prop = self._parse_text(text)
            
            if prop.survey_no:  # Only add if we found survey number
                properties.append(prop)
        
        return properties
    
    def _parse_text(self, text: str) -> ExtractedProperty:
        """Parse extracted text"""
        import re
        
        prop = ExtractedProperty(owners=[])
        
        # Survey number patterns
        patterns = [
            r'Survey\s*(?:No\.?|Number)?\s*[:\-]?\s*([\d/]+)',
            r'S\.?N\.?\s*[:\-]?\s*([\d/]+)',
            r'CTS\s*(?:No\.?)?\s*[:\-]?\s*([\d/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                prop.survey_no = match.group(1)
                break
        
        # Area
        area_match = re.search(r'(\d+[\.,]?\d*)\s*(Sq\.?|Square)?\s*(Meter|M\.?|m)', text, re.I)
        if area_match:
            prop.plot_area_sq_m = float(area_match.group(1).replace(",", ""))
            prop.plot_area_sq_ft = prop.plot_area_sq_m * 10.764
        
        # Road width
        road_match = re.search(r'(\d+\.?\d*)\s*m\.?\s*(?:Road|R\/W|W)', text, re.I)
        if road_match:
            prop.road_width_m = float(road_match.group(1))
        
        # Zone
        if "Residential" in text:
            prop.zone_type = "Residential"
        elif "Commercial" in text:
            prop.zone_type = "Commercial"
        elif "Industrial" in text:
            prop.zone_type = "Industrial"
        
        # Village
        village_match = re.search(r'Village\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|Taluka)', text, re.I)
        if village_match:
            prop.village = village_match.group(1).strip()
        
        return prop

# Usage
if __name__ == "__main__":
    ocr = PropertyCardOCR()
    
    # Process image
    # prop = ocr.extract_from_image("property_card.jpg")
    
    # Process PDF
    # props = ocr.extract_from_pdf("property_card.pdf")
    
    print("Property Card OCR ready")
    print("Usage: ocr.extract_from_image('path/to/image.jpg')")
```

---

## Implementation 5: MCGM API (If Available)

```python
# File: integrations/mcgm_api.py

import requests

class MCGMAPI:
    """MCGM API Integration"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.mcgm.gov.in/api"
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        })
    
    def get_property_details(self, property_id: str) -> dict:
        """Get property details"""
        try:
            url = f"{self.base_url}/property/{property_id}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def check_building_plan_status(self, application_no: str) -> dict:
        """Check building plan status"""
        try:
            url = f"{self.base_url}/building-plan/status/{application_no}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_oc_status(self, oc_no: str) -> dict:
        """Get Occupation Certificate status"""
        try:
            url = f"{self.base_url}/oc/{oc_no}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
```

---

## When to Use Selenium (Last Resort)

Use Selenium ONLY when:

1. **Login Required** with JavaScript handling
2. **CAPTCHA Present** that requires browser interaction
3. **SPA Website** with no server-side rendering

### Selenium Setup (If Needed)

```bash
pip install selenium webdriver-manager
```

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run without GUI
    options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(
        ChromeDriverManager().install(),
        options=options
    )
    
    return driver

def scrape_with_selenium(url: str) -> str:
    driver = setup_driver()
    
    try:
        driver.get(url)
        
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        return driver.page_source
    
    finally:
        driver.quit()
```

---

## Summary: Implementation Priority

### Week 1: Start Here
1. ✅ **RERA Integration** - API exists, easy to implement
2. ✅ **WhatsApp Compliance Parser** - Just file import
3. ✅ **Property Card OCR** - Upload and extract

### Week 2: Next
4. **MCGM Tender Scraper** - Requires testing
5. **MCGM Property Lookup** - May need Selenium

### Week 3+: If Needed
6. **Bhulekh Integration** - Not possible without login
7. **Building Plan Status** - Requires DSC authentication

---

## Testing Checklist

```bash
# 1. Test RERA API
python -c "from integrations.rera_integration import RERAIntegration; r = RERAIntegration(); print(r.search_by_registration('P51800045641'))"

# 2. Test WhatsApp Parser
echo "1/15/2024, 9:30 AM - Updates: MahaRERA circular on deemed conveyance" > test.txt
python integrations/whatsapp_compliance.py

# 3. Test OCR (if easyocr installed)
python -c "from integrations.property_card_ocr import PropertyCardOCR; print('OCR ready')"
```
