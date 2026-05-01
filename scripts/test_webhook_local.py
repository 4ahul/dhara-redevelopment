"""Local Clerk webhook tester — crafts proper Svix-signed requests."""

import base64
import hashlib
import hmac
import json
import time
import httpx

WEBHOOK_SECRET = "whsec_C/R2VzHnZQwMRzv6HvUDrsldQwG94Jvt"
BASE_URL = "http://localhost:8000/api/webhooks/clerk"


def make_svix_headers(body: bytes, secret: str) -> dict:
    svix_id = f"msg_test_{int(time.time())}"
    svix_ts = str(int(time.time()))

    raw = secret.removeprefix("whsec_")
    key = base64.b64decode(raw)

    signed = f"{svix_id}.{svix_ts}.".encode() + body
    sig = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()

    return {
        "svix-id": svix_id,
        "svix-timestamp": svix_ts,
        "svix-signature": f"v1,{sig}",
        "Content-Type": "application/json",
    }


def send(event_type: str, data: dict):
    body = json.dumps({"type": event_type, "data": data}).encode()
    headers = make_svix_headers(body, WEBHOOK_SECRET)

    print(f"\n→ Sending {event_type}")
    r = httpx.post(BASE_URL, content=body, headers=headers)
    print(f"  Status : {r.status_code}")
    print(f"  Body   : {r.text}")


# ── Test events ──────────────────────────────────────────────────────────────

USER_CREATED = {
    "id": "user_test_webhook_001",
    "email_addresses": [{"email_address": "webhook_test@example.com"}],
    "first_name": "Webhook",
    "last_name": "Test",
    "image_url": None,
}

USER_UPDATED = {
    "id": "user_test_webhook_001",
    "email_addresses": [{"email_address": "webhook_test_updated@example.com"}],
    "first_name": "Webhook",
    "last_name": "Updated",
    "image_url": None,
}

SESSION_CREATED = {
    "id": "sess_test_001",
    "user_id": "user_test_webhook_001",
}

USER_DELETED = {
    "id": "user_test_webhook_001",
    "deleted": True,
}

if __name__ == "__main__":
    send("user.created", USER_CREATED)
    send("user.updated", USER_UPDATED)
    send("session.created", SESSION_CREATED)
    send("user.deleted", USER_DELETED)
