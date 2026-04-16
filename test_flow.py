import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMzQzNjJjOC0wNzU3LTQ3MDktODMwOC0zNTVjNzk0NTU2MzkiLCJlbWFpbCI6ImFkbWluQGRoYXJhYWkuY29tIiwicm9sZSI6ImFkbWluIiwibmFtZSI6IkRoYXJhIEFJIEFkbWluIiwiaWF0IjoxNzc2MTU1MTEwLCJleHAiOjE3NzYyNDE1MTAsImlzcyI6ImRoYXJhLWFpIn0.1vSGoycAwmJCzKpKmwDzMZXXJ1n-pVAjAJZp33Zu-m4"

# Society ID from database
society_id = "cf9dcb2e-f499-4548-9e73-179df7ea090a"

# Create a feasibility report
data = {"society_id": society_id}

r = requests.post(
    "http://localhost:8000/api/feasibility-reports",
    json=data,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
print("Create Report Response:", r.status_code)
print(r.json())
