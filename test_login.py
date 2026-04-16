import requests

r = requests.post(
    "http://localhost:8000/api/auth/admin/login",
    json={"email": "admin@dharaai.com", "password": "admin@123"},
)
print(r.json())
