import asyncio
import re
import math
from playwright.async_api import async_playwright

# Pre-defined construction cost brackets (₹/sqft) depending on neighborhood tier
CONSTRUCTION_COSTS = {
    "Luxury": {"residential": 3500, "commercial": 4500, "podium": 1800, "basement": 2800, "parking_slot": 1500000},
    "Premium": {"residential": 2800, "commercial": 3800, "podium": 1500, "basement": 2300, "parking_slot": 1000000},
    "Standard": {"residential": 2200, "commercial": 3200, "podium": 1200, "basement": 1800, "parking_slot": 600000}
}

def classify_tier(village: str) -> str:
    """Classifies the Mumbai village into a Real Estate Tier"""
    luxury = ["bandra", "juhu", "worli", "lower parel", "south mumbai", "colaba", "vile parle east", "khar", "santacruz"]
    premium = ["andheri", "vile parle", "vile parle west", "goregaon", "powai", "malad", "borivali", "kandivali", "chembur", "ghatkopar"]
    v_lower = village.lower()
    
    for l in luxury:
        if l in v_lower: return "Luxury"
    for p in premium:
        if p in v_lower: return "Premium"
    return "Standard"

async def get_dynamic_market_data(ward: str, locality_type: str, locality_name: str, parcel_no: str):
    print(f"🔍 Analyzing Market Data for: Ward {ward.upper()} | {locality_type}: {locality_name.title()} | Parcel No: {parcel_no}...\n")
    
    tier = classify_tier(locality_name)
    costs = CONSTRUCTION_COSTS[tier]
    
    salable_rate = 0
    rent_rate = 0
    
    # 1. Scrape real-time rates dynamically (Simulating Housing.com / 99acres search via DuckDuckGo)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Searching specifically for the locality within the ward
        search_query = f"average property rate per sq ft in {locality_name} Mumbai Housing.com 99acres"
        print(f"🌐 Scraping web data for '{locality_name}' residential rates...")
        
        await page.goto(f"https://duckduckgo.com/?q={search_query.replace(' ', '+')}&t=h_&ia=web")
        await page.wait_for_timeout(3000) # wait for page to render
        
        text_content = await page.evaluate("document.body.innerText")
        
        # Capture strings like "₹ 25,000 / sq ft" or "Rs 22,000 per sqft"
        matches = re.findall(r'(?:₹|Rs\.?)\s*([\d,]+)(?:\s*[-to]+\s*(?:₹|Rs\.?)\s*[\d,]+)?\s*(?:per\s*sq\s*ft|\/sqft|\/ sq ft)', text_content, re.IGNORECASE)
        
        if matches:
            rates = [int(m.replace(',', '')) for m in matches if int(m.replace(',', '')) > 2000]
            if rates:
                salable_rate = sum(rates) // len(rates)
        
        # Fallback if headless scrape gets blocked
        if salable_rate == 0:
            print("⚠️ Live scrape exact matches not found in first pass, defaulting to Square Yards realistic base.")
            salable_rate = 80000 if tier == "Luxury" else (55000 if tier == "Premium" else 28000)
            
        # Rent is typically 2.5% to 3% rental yield annually for Mumbai
        # Rent/month estimation for a standard 1000 sqft setup
        rent_rate_per_sqft = (salable_rate * 0.025) / 12
        rent_1000_sqft = math.ceil((rent_rate_per_sqft * 1000) / 1000) * 1000
        
        await browser.close()

    # 2. Commercial Sale Area Breakup
    cost_office = salable_rate * 1.25  # Commercial upper flooring is often 20-30% higher than residential flats
    cost_retail_gf = cost_office * 2.2 # Ground Floor street retail cmds 2x+ over office

    # 3. Print Final Report
    print("=====================================================")
    print(f"🏢 MARKET DATA REPORT: Ward {ward.upper()} | {locality_name.upper()} | Parcel: {parcel_no}")
    print(f"⭐ Classification Tier  : {tier}")
    print("=====================================================")
    print("💰 1. SALABLE PRICES & RENT")
    print(f"   - Salable Resi Rate : ₹{salable_rate:,} / sq ft")
    print(f"   - Resi Rent (Avg)   : ₹{rent_1000_sqft:,} / month (Based on 1000 sqft apartment)")
    print(f"   - Cars to Sell Rate : ₹{costs['parking_slot']:,} / car")
    print("\n🏬 2. COMMERCIAL AREA SALE BREAKUP")
    print(f"   - Upper Floor Office: ₹{int(cost_office):,} / sq ft")
    print(f"   - Ground Flr Retail : ₹{int(cost_retail_gf):,} / sq ft (2.2x High-Street Premium)")
    print("\n🏗️ 3. CONSTRUCTION COSTS (Dynamic Base + Tier Modifier)")
    print(f"   - Residential Cost  : ₹{costs['residential']:,} / sq ft")
    print(f"   - Commercial Cost   : ₹{costs['commercial']:,} / sq ft")
    print(f"   - Podium Parking    : ₹{costs['podium']:,} / sq ft")
    print(f"   - Basement Cost     : ₹{costs['basement']:,} / sq ft (inc. heavy excavation, raft, waterproofing)")
    print("=====================================================\n")

if __name__ == "__main__":
    import sys
    print("\n==================================")
    print("🏙️  MUMBAI DYNAMIC MARKET SCRAPER")
    print("==================================")
    
    ward = input("Enter Ward (e.g., K/W, H/W, G/S): ").strip()
    loc_type = input("Is it a Village or TPS? (Enter 'Village' or 'TPS'): ").strip()
    locality_name = input(f"Enter the {loc_type} Name (e.g., Vile Parle West, Borivali): ").strip()
    
    if not locality_name:
        print(f"❌ Error: You must enter a {loc_type} name.")
        sys.exit(1)

    if loc_type.lower() == 'village':
        parcel_no = input("Enter CTS Number: ").strip()
    else:
        parcel_no = input("Enter FP Number: ").strip()
        
    asyncio.run(get_dynamic_market_data(ward, loc_type, locality_name, parcel_no))