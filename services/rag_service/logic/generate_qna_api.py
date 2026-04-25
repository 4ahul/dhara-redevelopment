import os
import logging
os.environ["OPENAI_API_KEY"] = open(".env").read().split("OPENAI_API_KEY=")[1].split("\n")[0]

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import time
from openai import OpenAI

logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/api/query"

questions = [
    "What is the basic FSI for residential on 9m road?",
    "For 2500 sqm on 12m road, max FSI with premium?",
    "Explain FSI table for road widths 9m to 30m.",
    "What is premium FSI rate and calculation?",
    "How is terrace area counted in FSI?",
    "Basement FSI exemption limit?",
    "33(7) process for society redevelopment?",
    "Affordable housing percentage under 33(7)?",
    "Additional 15% FSI under 33(7)?",
    "33(7B) vs 33(7) comparison?",
    "Incentive FSI under 33(7B)?",
    "33(20B) SRA scheme eligibility?",
    "Parking for 100 residential flats?",
    "Parking dimensions and requirements?",
    "Marginal distances for 7 floor building?",
    "Maximum building height in PMC?",
    "TDR process from land surrender?",
    "Commercial FSI on 30m road?",
    "Ground floor commercial rules?",
    "Table 12 FSI values by road width?",
    "Society 75 members 5000 sqm 33(7B) process?",
    "Parking for 2BHK vs 3BHK units?",
    "Marginal distances for building above 24m?",
    "EV charging parking requirements?",
    "Tandem parking allowed conditions?",
]

logger.info(f"Processing {len(questions)} questions...")

results = []
for i, q in enumerate(questions, 1):
    try:
        resp = requests.post(API_URL, json={"question": q, "k": 5}, timeout=60)
        data = resp.json()
        
        context = "\n\n".join([r["text"][:500] for r in data.get("results", [])])
        
        prompt = f"""Based on DCPR 2034, answer this question:

Question: {q}

Context:
{context}

Provide detailed answer with specific values.
"""
        
        client = OpenAI()
        llm_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a DCPR 2034 expert."}, {"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=1500
        )
        
        answer = llm_resp.choices[0].message.content
        confidence = data["results"][0]["score"] if data.get("results") else 0
        
        results.append({
            "Q_No": i,
            "Question": q,
            "Answer": answer,
            "Confidence": f"{confidence:.0%}",
            "Source_Score": confidence,
        })
        
        logger.info(f"[{i}/{len(questions)}] ✓ {confidence:.0%}")
        time.sleep(0.5)

    except Exception as e:
        logger.error(f"[{i}/{len(questions)}] ✗ {str(e)[:40]}", exc_info=True)
        results.append({"Q_No": i, "Question": q, "Answer": f"Error: {str(e)}", "Confidence": "0%", "Source_Score": 0})

df = pd.DataFrame(results)
Path("data").mkdir(exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"data/PMC_QnA_{len(questions)}_{ts}.xlsx"
df.to_excel(filename, index=False)

passed = sum(1 for r in results if float(r['Confidence'].replace('%','')) >= 40)
logger.info(f"\nSAVED: {filename}")
logger.info(f"Total: {len(results)} | Answered: {passed} ({passed/len(results)*100:.0f}%)")

