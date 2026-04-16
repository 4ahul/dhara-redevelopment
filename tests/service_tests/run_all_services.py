import os
import subprocess
import sys

scripts = [
    "test_height_service.py",
    "test_mcgm_property_lookup.py",
    "test_pr_card_scraper.py",
    "test_site_analysis.py",
    "test_premium_checker.py",
    "test_orchestrator.py",
    "test_rag_service.py",
    "test_report_generator.py"
]

def run_all():
    print("=== DHARA AI SERVICE VERIFICATION ===")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    for script in scripts:
        print(f"\n>> Running {script}...")
        script_path = os.path.join(base_dir, script)
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"ERRORS in {script}:\n{result.stderr}")
    
    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    run_all()
