import asyncio
import os
import sys
import json
from pathlib import Path

# Add services/orchestrator to path to resolve imports
orch_path = os.path.abspath("services/orchestrator")
if orch_path not in sys.path:
    sys.path.append(orch_path)

# Mock env vars if needed
os.environ["REDIS_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql+asyncpg://redevelopment:redevelopment@localhost:5432/redevelopment")

# Import the runner
from agent.runner import run_agent, set_llm_client
from agent.llm_client import get_llm_client

async def test_full_pipeline():
    print("🚀 Starting Full Pipeline Test for Dhiraj Kunj...")
    
    # Dhiraj Kunj Input (minimal, relying on our hardcoded defaults)
    society_data = {
        "society_name": "Dhiraj Kunj CHS",
        "address": "Dhiraj Kunj, 40-41, Bajaj Road, Vile Parle West, Mumbai, Maharashtra 400056",
        "cts_no": "854",
        "ward": "K/W",
        "village": "VILE PARLE"
    }

    # Initialize LLM Client
    client = get_llm_client()
    set_llm_client(client)
    print(f"Using LLM: {client.get_model_name()}")

    try:
        # Run the agent
        print("Running Agent (this will take a few minutes)...")
        result = await run_agent(society_data, request_id="TEST-FULL-FLOW-001")
        
        print("\n✅ Analysis Complete!")
        print(f"Status: {result.get('status')}")
        print(f"Report Path: {result.get('report_path')}")
        print(f"Reports Generated: {result.get('reports_count')}")
        
        # Save result to file for inspection
        with open("pipeline_test_result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print("Detailed results saved to pipeline_test_result.json")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
