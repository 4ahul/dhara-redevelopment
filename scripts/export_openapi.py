import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SERVICES = [
    "orchestrator",
    "aviation_height",
    "dp_remarks_report",
    "mcgm_property_lookup",
    "pr_card_scraper",
    "rag_service",
    "ready_reckoner",
    "report_generator",
    "site_analysis",
]

def export_openapi():
    output_dir = ROOT / "docs" / "api"
    output_dir.mkdir(parents=True, exist_ok=True)

    for service in SERVICES:
        print(f"Exporting OpenAPI for {service}...")
        service_dir = ROOT / "services" / service
        output_file = output_dir / f"{service}.json"
        
        # Command to run inside the service dir using its own environment
        # We use uv run to ensure it has the correct dependencies
        cmd = [
            "uv", "run", "python", "-c",
            f"import json; from main import app; print(json.dumps(app.openapi(), indent=2))"
        ]
        
        try:
            # Set environment variables for initialization
            env = os.environ.copy()
            env["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost:5432/db"
            env["SECRET_KEY"] = "mock_secret"
            env["GEMINI_API_KEY"] = "mock_key"
            env["GOOGLE_MAPS_API_KEY"] = "AIzaSyA" + "X" * 32
            env["SERP_API_KEY"] = "mock_key"
            
            # Add root to PYTHONPATH so dhara_shared is importable
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            
            result = subprocess.run(
                cmd,
                cwd=service_dir,
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode == 0:
                with open(output_file, "w") as f:
                    f.write(result.stdout)
                print(f"  [OK] Saved to docs/api/{service}.json")
            else:
                print(f"  [FAIL] {service} failed: {result.stderr}")
                
        except Exception as e:
            print(f"  [ERROR] {service}: {e}")

if __name__ == "__main__":
    export_openapi()
