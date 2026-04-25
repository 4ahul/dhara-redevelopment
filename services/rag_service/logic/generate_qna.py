import os
os.environ["HF_TOKEN"] = "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"

from .intelligent_rag import IntelligentRAG
import pandas as pd
from pathlib import Path
from datetime import datetime

print("Starting Q&A generation...")

rag = IntelligentRAG()

# 100 hard PMC questions
questions = [
    # FSI Complex
    "For a residential plot of 2500 sqm in Wakad on 12m road, calculate exact FSI breakdown including basic, premium and fungible options with charges.",
    "What is the exact premium FSI rate as percentage of ASR and how is it calculated for additional FSI beyond basic?",
    "Explain how terrace area, basement area, stilt floor area are counted or exempted in FSI calculation.",
    "For a plot partially in residential and partially in commercial zone, how is FSI calculated?",
    "What is the maximum FSI possible for 5000 sqm plot on 30m road with all premium options including TDR?",
    
    # Scheme 33(7)
    "Society has 80 members on 4500 sqm in Baner, explain complete 33(7) process from application to possession.",
    "What is the mandatory 10% social housing under 33(7), who receives it and what is the process?",
    "Can society members opt for additional area beyond their existing and what is the limit?",
    "What happens to tenants who refuse to participate in 33(7) redevelopment?",
    "What are the exact timelines for vacating, constructing and handing over under 33(7)?",
    
    # Scheme 33(7B)
    "Compare 33(7) vs 33(7B) for 5000 sqm society with 100 members including FSI, timeline and financial aspects.",
    "What is the 15% incentive FSI under 33(7B) and how is it calculated on existing built-up area?",
    "Explain the composite redevelopment option under 33(7B) for multiple adjacent societies.",
    "What additional benefits does 33(7B) provide compared to 33(7)?",
    
    # Scheme 33(20B) SRA
    "For slum rehabilitation in Govandi, explain 33(20B) eligibility, FSI breakdown and rehab-sale ratio.",
    "Who qualifies as eligible slum dweller and what is the verification process?",
    "What is plot to PCR TDR transfer and how does it work under 33(20B)?",
    "What are the timeline obligations and penalties for delays in SRA projects?",
    
    # Parking Complex
    "For residential with 120 flats (40 x 1BHK 500sqft, 50 x 2BHK 750sqft, 30 x 3BHK 1000sqft), calculate exact parking requirement.",
    "What are dimensions for standard, compact and EV charging parking slots including maneuvering space?",
    "Is tandem parking allowed, what percentage can be tandem and what are conditions?",
    "How is visitor parking calculated and what percentage of total is required?",
    "What are parking requirements for basement, stilt and podium levels?",
    
    # Margins Complex
    "For stilt+10 floors on 800 sqm plot on 12m road, explain marginal distances for each floor and total open space required.",
    "How do marginal distances change at heights 15m, 24m, 32m, 50m and 70m?",
    "What is minimum distance from building to plot boundary on each side for 7 floor building?",
    "How are marginal distances affected when adjacent building is taller?",
    "What setback relaxations are available for plots less than 300 sqm?",
    
    # TDR Complex
    "Explain complete TDR certificate process from land surrender to utilization in receiving area.",
    "What is the formula for calculating TDR quantity based on surrendered land area?",
    "What are designated sending areas and can any area generate TDR?",
    "What is the validity period and can unused TDR be extended?",
    "What is stamp duty implication and how is TDR price determined in market?",
    
    # Commercial Complex
    "For IT park building on 5000 sqm with 30m road, explain FSI, parking, setback and amenity requirements.",
    "What are loading-unloading bay requirements for commercial complex with multiple tenancies?",
    "How is parking calculated for shopping mall with 200 shops and 5 screens cinema?",
    "What percentage of floor area can be used for basement parking?",
    
    # Height Complex
    "What is exact formula for maximum building height based on road width and zone?",
    "How is building height measured and what includes in height calculation?",
    "What are conditions for constructing stilts and does stilt floor count in FSI?",
    "Explain podium construction rules and how podium FSI is calculated.",
    "Can terrace be covered and what percentage coverage is allowed?",
    
    # Mixed Use
    "What ground floor activities are permitted in residential zone and which are prohibited?",
    "Can restaurant, clinic, gym and shop operate on ground floor in residential zone?",
    "What is the process to obtain mixed use permission in PMC?",
    "How does ground floor commercial usage affect residential FSI?",
    
    # Reconstruction
    "For 50 year old RC cement building in Dadar, what regulations apply for reconstruction?",
    "What structural stability certificate is required and from whom?",
    "Can reconstruction avail any additional FSI or scheme benefits?",
    
    # Tables
    "Explain in detail all values in Table 12 for FSI by road width from 9m to 60m.",
    "What are exact marginal distances in Table 18 for heights up to 100m?",
    "Detail all parking requirements from Table 21 including two-wheeler and visitor.",
    
    # Environmental
    "What are rainwater harvesting requirements based on plot size?",
    "Explain STP capacity calculation based on population and type of building.",
    "What percentage of electricity load must come from solar?",
    
    # Compliance
    "List all NOCs required for starting construction with approval authority and timeline.",
    "What are fire safety requirements for buildings above 24m including hydrants and extinguishers?",
    "Explain accessibility requirements for wheelchair users in residential buildings.",
    "What are staircase dimensions and number required based on occupancy?",
    
    # Financial
    "Calculate total project cost including construction, premiums, charges and approvals for 4000 sqm residential.",
    "What is per sqft construction cost in Pune 2024 for basic, medium and premium specification?",
    "Explain all government charges including scrutiny fee, premium charges and deposits.",
    
    # Advanced
    "What happens when FSI utilized exceeds approved limit during construction?",
    "Can FSI be transferred between two different projects of same developer?",
    "What are penalties for construction without proper approvals?",
    "How does RERA registration affect project timelines and completion certificates?",
    
    # More Schemes
    "What is 33(7A) transit oriented development benefit for plots near metro?",
    "Explain benefits of 33(7A) including additional FSI and relaxation in margins.",
    
    # More Tables
    "What information does Table 22 contain regarding open space reservation?",
    "What are height limits in Table 23 for different road widths?",
    
    # More Complex
    "For 2000 sqm corner plot on 18m road, what is maximum FSI with all premium options?",
    "Compare financial viability of 33(7) vs 33(7B) vs normal redevelopment for 3000 sqm society.",
    "What is total approval cost including all premiums and charges for 5000 sqm commercial project?",
    
    # SRA Details
    "What is free sale area in SRA project and how is it calculated?",
    "Can SRA developer sell at market rate or is there price control?",
    
    # Parking More
    "What are parking requirements for hospital with 200 beds?",
    "How is parking calculated for school with 1000 students?",
    
    # Margins More
    "What is minimum distance between two buildings on same plot?",
    "How are margins affected if building is on plot boundary?",
    
    # FSI More
    "What is fungible FSI limit and how is premium calculated?",
    "Can fungible and premium FSI be combined?",
    
    # TDR More
    "What is floor space index certificate and how is it obtained?",
    "Can TDR be used for any building or only in receiving areas?",
    
    # Approval More
    "What is OC application process and what documents are required?",
    "How is compound wall approval obtained separately?",
    
    # Reconstruction More
    "What is meaning of dangerous or dilapidated building as per DCPR?",
    "Can heritage building be reconstructed with additional FSI?",
    
    # Open Space More
    "What is amenity space requirement per 100 sqm plot?",
    "Can OSR be on multiple plots in layout?",
    
    # More Compliance
    "What are excavation and foundation rules near adjacent building?",
    "What structural audit is required for buildings above 30 years?",
    
    # More Height
    "What is maximum floor height for residential and commercial?",
    "Can building exceed height if setbacks are increased?",
    
    # More Parking
    "What are two-wheeler parking requirements?",
    "Is servant quarter parking separate from resident parking?",
    
    # More TDR
    "What is TDR utilization certificate?",
    "Can TDR be purchased from another developer?",
    
    # More Schemes
    "What is compound scheme involving 33(7) plus TDR?",
    "Can multiple schemes be combined for maximum benefit?",
    
    # More Financial
    "What is MCGM scrutiny fee structure?",
    "How are development charges calculated?",
]

print(f"Total questions: {len(questions)}")

results = []
for i, q in enumerate(questions, 1):
    try:
        print(f"[{i}/{len(questions)}] Processing: {q[:50]}...")
        r = rag.query(q)
        results.append({
            "Q_No": i,
            "Question": q,
            "Answer": r['answer'],
            "Confidence": f"{r['confidence']:.0%}",
            "Clauses": ", ".join(r['clauses_found'][:5]),
            "Tables": ", ".join(r['tables_found'][:3]),
        })
    except Exception as e:
        print(f"Error: {e}")
        results.append({
            "Q_No": i,
            "Question": q,
            "Answer": f"Error: {str(e)}",
            "Confidence": "0%",
            "Clauses": "",
            "Tables": "",
        })

# Save
df = pd.DataFrame(results)
Path("data").mkdir(exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"data/PMC_100_HardQnA_{ts}.xlsx"
df.to_excel(filename, index=False)

passed = sum(1 for r in results if float(r['Confidence'].replace('%','')) >= 30)
print(f"\n{'='*60}")
print(f"SAVED: {filename}")
print(f"Total: {len(results)} | Answered (>=30%): {passed} ({passed/len(results)*100:.1f}%)")
print("DONE!")

