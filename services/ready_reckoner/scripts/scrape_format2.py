import json
import re
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

BASE_URL = "https://www.e-stampdutyreadyreckoner.com"
YEAR = "2026"
DISTRICTS = ["mumbai", "mumbai-suburban"]

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "extracted", "ready_reckoner_rates"))
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR, f"rr_rates_{YEAR}.jsonl")

def parse_date(date_str):
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    try:
        dt = datetime.strptime(clean_date.strip(), '%d %B %Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return date_str

def get_locality_links(page, district):
    page.goto(f"{BASE_URL}/reckoner/{YEAR}/{district}", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    
    hrefs = page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
    # Extract talukas
    talukas = set()
    for h in hrefs:
        match = re.search(rf"/reckoner/{YEAR}/{district}/([\w-]+)$", h)
        if match:
            talukas.add(match.group(1))
            
    locality_links = []
    for taluka in talukas:
        page.goto(f"{BASE_URL}/reckoner/{YEAR}/{district}/{taluka}", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        t_hrefs = page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
        for h in t_hrefs:
            if re.search(rf"/reckoner/{YEAR}/{district}/{taluka}/([\w-]+)$", h):
                locality_links.append(h)
    
    return list(set(locality_links))

def extract_properties(html, url_meta):
    soup = BeautifulSoup(html, "html.parser")
    properties = []
    
    fieldsets = soup.find_all("fieldset", class_="innerfieldset")
    
    for fieldset in fieldsets:
        table = fieldset.find("table", class_="rate-table")
        if not table:
            continue
            
        record = {
            "location": {
                "district": url_meta["district"],
                "taluka": url_meta["taluka"],
                "locality": url_meta["locality"],
                "village": "",
                "zone": "",
                "sub_zone": "",
                "cts_no": "",
                "plot_no": ""
            },
            "administrative": {
                "type_of_area": "",
                "local_body_name": "",
                "local_body_type": ""
            },
            "applicability": {
                "commence_from": "",
                "commence_to": "",
                "landmark_note": ""
            },
            "rates": []
        }
        
        rows = table.find_all("tr")
        for tr in rows:
            text = tr.get_text(separator=" ", strip=True)
            
            # Simple village extraction
            if "VILLAGE :" in text.upper():
                v_match = re.search(r'VILLAGE\s*:\s*(.*?)(Commence From|$)', text, re.IGNORECASE)
                if v_match:
                    record["location"]["village"] = v_match.group(1).strip()
                
                d_match = re.search(r'Commence From\s*(.*?)\s*To\s*(.*)', text, re.IGNORECASE)
                if d_match:
                    record["applicability"]["commence_from"] = parse_date(d_match.group(1))
                    record["applicability"]["commence_to"] = parse_date(d_match.group(2))
            
            ths = tr.find_all("th")
            tds = tr.find_all("td")
            
            if len(ths) >= 1 and len(tds) >= 1:
                if "Type of Area" in ths[0].get_text():
                    record["administrative"]["type_of_area"] = tds[0].get_text(strip=True)
                if len(ths) >= 2 and "Local Body Type" in ths[1].get_text():
                    record["administrative"]["local_body_type"] = tds[1].get_text(strip=True).replace('“', "'").replace('”', "'").replace('"', "'")
                if "Local Body Name" in ths[0].get_text():
                    record["administrative"]["local_body_name"] = tds[0].get_text(strip=True)
                if "Land Mark" in ths[0].get_text():
                    lm = tds[0].get_text(strip=True)
                    if lm.startswith("Terrain:"):
                        lm = lm[8:].strip()
                    record["applicability"]["landmark_note"] = lm

        # Zone and Sub Zone
        zone_headers = []
        zone_values = []
        for tr in rows:
            ths = tr.find_all("th")
            if ths and ths[0].get_text(strip=True) == "Zone":
                zone_headers = [th.get_text(strip=True) for th in ths]
                next_tr = tr.find_next_sibling("tr")
                if next_tr:
                    tds = next_tr.find_all("td")
                    zone_values = [td.get_text(strip=True) for td in tds]
                break
                
        if zone_headers and zone_values:
            for i, h in enumerate(zone_headers):
                if h == "Zone" and i < len(zone_values):
                    record["location"]["zone"] = zone_values[i]
                elif h == "Sub Zone" and i < len(zone_values):
                    record["location"]["sub_zone"] = zone_values[i]

        # CTS No and Plot No
        textarea_td = table.find("td", class_="table-texarea")
        if textarea_td:
            div = textarea_td.find("div")
            if div:
                for strong in div.find_all("strong"):
                    key = strong.get_text(strip=True).replace(":", "").strip()
                    next_node = strong.next_sibling
                    val = ""
                    if next_node and isinstance(next_node, str):
                        val = next_node.strip().rstrip(",")
                    if key.upper() == "CTS NO.":
                        record["location"]["cts_no"] = val
                    elif key.upper() == "PLOT NO.":
                        record["location"]["plot_no"] = val

        # Rates
        def get_val(id_pattern):
            node = fieldset.find("input", id=re.compile(id_pattern))
            return int(node["value"]) if node and node.get("value") else 0

        c_land = get_val(r"landc\d+")
        p_land = get_val(r"landp\d+")
        c_res = get_val(r"residentalc\d+")
        p_res = get_val(r"residentalp\d+")
        c_off = get_val(r"officec\d+")
        p_off = get_val(r"officep\d+")
        c_shop = get_val(r"shopc\d+")
        p_shop = get_val(r"shopp\d+")
        c_ind = get_val(r"industrialc\d+")
        p_ind = get_val(r"industrialp\d+")

        def make_rate(category, curr_val, prev_val):
            inc_amt = curr_val - prev_val
            inc_pct = round((inc_amt / prev_val) * 100, 2) if prev_val > 0 else 0.0
            return {
                "category": category,
                "value": curr_val,
                "previous_year_rate": prev_val,
                "increase_amount": inc_amt,
                "increase_or_decrease_percent": inc_pct
            }

        record["rates"] = [
            make_rate("Land", c_land, p_land),
            make_rate("Residential", c_res, p_res),
            make_rate("Office", c_off, p_off),
            make_rate("Shop", c_shop, p_shop),
            make_rate("Industrial", c_ind, p_ind)
        ]
        
        properties.append(record)
    return properties

def main():
    print(f"Starting scraper. Output will be written to {OUT_FILE}")
    # Initialize file (truncate if exists)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        pass
        
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        all_links = []
        for district in DISTRICTS:
            print(f"Discovering links for district: {district}")
            links = get_locality_links(page, district)
            print(f"Found {len(links)} links in {district}")
            all_links.extend(links)
            
        print(f"Total localities to scrape: {len(all_links)}")
        
        count = 0
        total = len(all_links)
        
        with open(OUT_FILE, "a", encoding="utf-8") as f:
            for url in all_links:
                parts = url.rstrip("/").split("/")
                meta = {
                    "district": parts[-3],
                    "taluka": parts[-2],
                    "locality": parts[-1]
                }
                
                print(f"[{count+1}/{total}] Scraping {meta['district']} -> {meta['taluka']} -> {meta['locality']}")
                
                retries = 3
                success = False
                while retries > 0 and not success:
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000) # Give time for JS to populate hidden inputs
                        html = page.content()
                        
                        props = extract_properties(html, meta)
                        for p in props:
                            f.write(json.dumps(p) + "\n")
                            
                        print(f"   -> Extracted {len(props)} properties.")
                        success = True
                        
                    except Exception as e:
                        print(f"   -> Error on {url}: {e}. Retrying...")
                        retries -= 1
                        time.sleep(2)
                
                count += 1
                
        browser.close()
        print("Done scraping!")

if __name__ == "__main__":
    main()
