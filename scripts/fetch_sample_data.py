"""
Dhara AI — Fetch Sample Data from All Microservices
====================================================
Run this script with docker-compose services up.
It calls every microservice with a real test property and dumps the responses.

Usage:
    python scripts/fetch_sample_data.py
    python scripts/fetch_sample_data.py --address "Dhiraj Kunj, Bajaj Road, Vile Parle West"
    python scripts/fetch_sample_data.py --output sample_data.json

This gives you the raw data an agent would have when deciding
which DCPR 2034 regulations apply to a property.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

import httpx

# ─── Service URLs (Docker Compose defaults) ─────────────────────────────────
ORCHESTRATOR_URL = "http://localhost:8000"
RAG_URL          = "http://localhost:8006"

# ─── Test Property (Vile Parle — good coverage across all services) ──────────
DEFAULT_PROPERTY = {
    "society_name": "Dhiraj Kunj CHS",
    "address": "Dhiraj Kunj, 40-41, Bajaj Road, Vile Parle West, Mumbai, Maharashtra 400056",
    "cts_no": "854",
    "fp_no": None,
    "ward": "K/W",
    "village": "VILE PARLE",
    "tps_name": None,
    "use_fp_scheme": False,
    "scheme": "33(7)(B)",
    "redevelopment_type": "CLUBBING",
    "num_flats": 20,
    "num_commercial": 0,
    "society_age": 40,
    "existing_bua_sqft": 12000.0,
    "plot_area_sqm": 800.0,
    "road_width_m": 12.0,
}


async def check_health(client: httpx.AsyncClient, url: str, name: str) -> bool:
    """Check if a service is up."""
    try:
        r = await client.get(f"{url}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


async def fetch_all_sample_data(property_data: dict, output_file: str | None = None):
    """Call all microservices and collect their responses."""

    results = {
        "_meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "property": property_data,
            "description": "Sample data from all Dhara microservices for DCPR regulation matching",
        },
        "services": {},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:

        # ── 1. Health Check ──────────────────────────────────────────────
        print("\n=== Health Checks ===")
        services = {
            "orchestrator": ORCHESTRATOR_URL,
            "rag_service": RAG_URL,
        }
        for name, url in services.items():
            up = await check_health(client, url, name)
            status = "UP" if up else "DOWN"
            print(f"  {name:25s} {status}")
            if not up:
                print(f"    WARNING: {name} is down. Its data will be missing.")

        # ── 2. Full Orchestrator Analysis (Round 1 + Round 2) ────────────
        print("\n=== Calling Orchestrator /api/feasibility-reports/analyze ===")
        print("  This triggers ALL downstream microservices (PR Card, MCGM, DP Remarks,")
        print("  Site Analysis, Aviation Height, Ready Reckoner, Report Generator)...")
        print("  (This may take 30-60 seconds)")

        try:
            r = await client.post(
                f"{ORCHESTRATOR_URL}/api/feasibility-reports/analyze",
                json=property_data,
                timeout=300.0,
            )
            r.raise_for_status()
            analyze_data = r.json()
            results["services"]["orchestrator_analyze"] = analyze_data

            # Extract individual service results from the response
            r1 = analyze_data.get("round1_results", {})
            r2 = analyze_data.get("round2_results", {})

            results["services"]["pr_card"]         = r1.get("pr_card", {})
            results["services"]["mcgm_property"]   = r1.get("mcgm", {})
            results["services"]["site_analysis"]   = r1.get("site_analysis", {})
            results["services"]["dp_remarks"]      = r1.get("dp_remarks", {})
            results["services"]["aviation_height"] = r2.get("aviation_height", {})
            results["services"]["ready_reckoner"]  = r2.get("ready_reckoner", {})

            print(f"  Status: {analyze_data.get('status')}")
            print(f"  Job ID: {analyze_data.get('job_id')}")
            if analyze_data.get("report_url"):
                print(f"  Report URL: {analyze_data['report_url']}")

            # Print summary of each service
            print("\n  --- Round 1 Results ---")
            for svc in ["pr_card", "mcgm", "site_analysis", "dp_remarks"]:
                data = r1.get(svc, {})
                if "error" in data:
                    print(f"    {svc:25s} ERROR: {data['error'][:80]}")
                else:
                    keys = list(data.keys())[:5]
                    print(f"    {svc:25s} OK ({len(data)} fields: {', '.join(keys)}...)")

            print("\n  --- Round 2 Results ---")
            for svc in ["aviation_height", "ready_reckoner"]:
                data = r2.get(svc, {})
                if "error" in data:
                    print(f"    {svc:25s} ERROR: {data['error'][:80]}")
                else:
                    keys = list(data.keys())[:5]
                    print(f"    {svc:25s} OK ({len(data)} fields: {', '.join(keys)}...)")

        except httpx.TimeoutException:
            print("  TIMEOUT — analysis took too long. Try again or check service logs.")
            results["services"]["orchestrator_analyze"] = {"error": "timeout"}
        except Exception as e:
            print(f"  ERROR: {e}")
            results["services"]["orchestrator_analyze"] = {"error": str(e)}

        # ── 3. RAG Service — Regulation Queries ──────────────────────────
        print("\n=== Calling RAG Service /api/query ===")
        print("  Querying DCPR 2034 regulations relevant to this property...")

        # Build regulation queries from the collected data
        dp_data = results["services"].get("dp_remarks", {})
        zone = dp_data.get("zone_code", dp_data.get("zone", "R1"))
        road_width = dp_data.get("road_width_m", property_data.get("road_width_m", 12))
        plot_area = property_data.get("plot_area_sqm", 800)

        rag_queries = [
            f"What DCPR 2034 regulations apply to redevelopment under Regulation 33(7)(B) for a society in {zone} zone with plot area {plot_area} sqm and road width {road_width}m?",
            f"What is the permissible FSI for redevelopment under DCPR 2034 Regulation 33(7)(B) in zone {zone}?",
            f"What are the TDR and premium requirements under DCPR 2034 for {property_data.get('scheme', '33(7)(B)')} redevelopment?",
            "What are the parking requirements under DCPR 2034 for residential redevelopment?",
            "What height restrictions apply under DCPR 2034 based on road width and aviation NOC?",
        ]

        results["services"]["rag_regulations"] = []

        for i, query in enumerate(rag_queries, 1):
            print(f"\n  Query {i}: {query[:80]}...")
            try:
                r = await client.post(
                    f"{RAG_URL}/api/query",
                    json={"query": query},
                    timeout=120.0,
                )
                r.raise_for_status()
                rag_data = r.json()
                results["services"]["rag_regulations"].append({
                    "query": query,
                    "answer": rag_data.get("answer", ""),
                    "sources": rag_data.get("sources", []),
                    "clauses": rag_data.get("clauses", []),
                    "confidence": rag_data.get("confidence"),
                })
                # Trim for display
                answer_preview = (rag_data.get("answer", "")[:120] + "...") if rag_data.get("answer") else "No answer"
                clauses = rag_data.get("clauses", [])
                print(f"    Answer: {answer_preview}")
                print(f"    Clauses: {clauses}")
                print(f"    Confidence: {rag_data.get('confidence')}")
            except Exception as e:
                print(f"    ERROR: {e}")
                results["services"]["rag_regulations"].append({
                    "query": query,
                    "error": str(e),
                })

        # ── 4. Summary ───────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("SAMPLE DATA COLLECTION COMPLETE")
        print("=" * 70)

        # Build the agent context — what an agent would see
        agent_context = {
            "property": property_data,
            "plot_data": {
                "cts_no": property_data.get("cts_no"),
                "ward": property_data.get("ward"),
                "village": property_data.get("village"),
                "plot_area_sqm": plot_area,
                "road_width_m": road_width,
            },
            "dp_remarks": results["services"].get("dp_remarks", {}),
            "mcgm_data": results["services"].get("mcgm_property", {}),
            "aviation": results["services"].get("aviation_height", {}),
            "ready_reckoner": results["services"].get("ready_reckoner", {}),
            "regulations": [
                {
                    "query": r.get("query"),
                    "answer": r.get("answer"),
                    "clauses": r.get("clauses"),
                }
                for r in results["services"].get("rag_regulations", [])
                if "error" not in r
            ],
        }
        results["agent_context"] = agent_context

        # Save to file
        out = output_file or "sample_microservice_data.json"
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nFull data saved to: {out}")
        print(f"  Total size: {len(json.dumps(results, default=str))} bytes")
        print(f"\nUse results['agent_context'] as input to your regulation-matching agent.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch sample data from all Dhara microservices")
    parser.add_argument("--address", help="Property address to analyze")
    parser.add_argument("--cts", help="CTS number")
    parser.add_argument("--ward", help="Ward code (e.g. K/W)")
    parser.add_argument("--village", help="Village name")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    args = parser.parse_args()

    prop = DEFAULT_PROPERTY.copy()
    if args.address:
        prop["address"] = args.address
    if args.cts:
        prop["cts_no"] = args.cts
    if args.ward:
        prop["ward"] = args.ward
    if args.village:
        prop["village"] = args.village

    asyncio.run(fetch_all_sample_data(prop, args.output))
