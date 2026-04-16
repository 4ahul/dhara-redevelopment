import os

os.environ["HF_TOKEN"] = "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"

from intelligent_rag import IntelligentRAG
import pandas as pd
from pathlib import Path
from datetime import datetime

rag = IntelligentRAG()

questions = [
    "What is basic FSI for residential on 9m road?",
    "Max FSI for 2500 sqm on 12m road?",
    "Explain 33(7) scheme for societies?",
    "Parking requirements for 100 flats?",
    "Marginal distances for 7 floors?",
    "TDR process explained?",
    "What is premium FSI?",
    "33(7B) vs 33(7) comparison?",
    "Maximum building height?",
    "Table 12 FSI values?",
    "Basement FSI exemption?",
    "Terrace area in FSI?",
    "Affordable housing under 33(7)?",
    "Parking dimensions?",
    "Tandem parking allowed?",
    "Ground floor commercial rules?",
    "33(20B) SRA scheme?",
    "Open space requirements?",
    "Height for different road widths?",
    "TDR certificate process?",
]

print(f"Processing {len(questions)} questions...")

results = []
for i, q in enumerate(questions, 1):
    print(f"[{i}/{len(questions)}] {q[:40]}...", end=" ")
    try:
        r = rag.query(q)
        results.append(
            {
                "Q_No": i,
                "Question": q,
                "Answer": r["answer"],
                "Confidence": f"{r['confidence']:.0%}",
            }
        )
        print(f"✓ {r['confidence']:.0%}")
    except Exception as e:
        print(f"✗ {str(e)[:30]}")
        results.append(
            {"Q_No": i, "Question": q, "Answer": f"Error: {str(e)}", "Confidence": "0%"}
        )

df = pd.DataFrame(results)
Path("data").mkdir(exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"data/PMC_QA_{len(questions)}_{ts}.xlsx"
df.to_excel(filename, index=False)

passed = sum(1 for r in results if float(r["Confidence"].replace("%", "")) >= 30)
print(f"\nSAVED: {filename}")
print(f"Total: {len(results)} | Answered: {passed}")
