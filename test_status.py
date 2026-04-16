import requests
import time

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMzQzNjJjOC0wNzU3LTQ3MDktODMwOC0zNTVjNzk0NTU2MzkiLCJlbWFpbCI6ImFkbWluQGRoYXJhYWkuY29tIiwicm9sZSI6ImFkbWluIiwibmFtZSI6IkRoYXJhIEFJIEFkbWluIiwiaWF0IjoxNzc2MTU1MTEwLCJleHAiOjE3NzYyNDE1MTAsImlzcyI6ImRoYXJhLWFpIn0.1vSGoycAwmJCzKpKmwDzMZXXJ1n-pVAjAJZp33Zu-m4"

report_id = "79dce498-a55e-4886-9682-a248200dfdfe"

# Wait for background task to process
time.sleep(5)

# Get the report status
r = requests.get(
    f"http://localhost:8000/api/feasibility-reports/{report_id}",
    headers={"Authorization": f"Bearer {token}"},
)
print("Report Status:", r.status_code)
result = r.json()
print("Status:", result.get("status"))
print("Error:", result.get("error_message"))
print(
    "Output Data:",
    result.get("output_data")[:500] if result.get("output_data") else "None",
)
print(
    "LLM Analysis:",
    result.get("llm_analysis")[:500] if result.get("llm_analysis") else "None",
)
