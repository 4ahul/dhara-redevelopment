import requests
import time

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMzQzNjJjOC0wNzU3LTQ3MDktODMwOC0zNTVjNzk0NTU2MzkiLCJlbWFpbCI6ImFkbWluQGRoYXJhYWkuY29tIiwicm9sZSI6ImFkbWluIiwibmFtZSI6IkRoYXJhIEFJIEFkbWluIiwiaWF0IjoxNzc2MTU1MTEwLCJleHAiOjE3NzYyNDE1MTAsImlzcyI6ImRoYXJhLWFpIn0.1vSGoycAwmJCzKpKmwDzMZXXJ1n-pVAjAJZp33Zu-m4"

report_id = "79dce498-a55e-4886-9682-a248200dfdfe"

# Wait for background task to process
print("Waiting for report processing...")
for i in range(12):
    time.sleep(5)
    r = requests.get(
        f"http://localhost:8000/api/feasibility-reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    result = r.json()
    status = result.get("status")
    print(f"Attempt {i + 1}: Status = {status}")
    if status in ["completed", "failed"]:
        break

# Final check
r = requests.get(
    f"http://localhost:8000/api/feasibility-reports/{report_id}",
    headers={"Authorization": f"Bearer {token}"},
)
result = r.json()
print("\n=== Final Report ===")
print("Status:", result.get("status"))
print("Error:", result.get("error_message"))
if result.get("output_data"):
    print("Output Data (first 1000 chars):", str(result.get("output_data"))[:1000])
if result.get("llm_analysis"):
    print("LLM Analysis (first 1000 chars):", str(result.get("llm_analysis"))[:1000])
