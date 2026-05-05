# Razorpay Payment Integration — Frontend API Guide

**Base URL:** `http://localhost:8000` (local) or `https://orchestrator-a2q7.onrender.com` (deployed)

**Auth:** All endpoints except webhook require `Authorization: Bearer <clerk_token>`

---

## Quick Summary

| # | Method | Endpoint | Purpose | Auth |
|---|--------|----------|---------|------|
| 1 | POST | `/api/subscription/status` | Check if user has active subscription | Yes |
| 2 | POST | `/api/subscription/checkout` | Create Razorpay order (start payment) | Yes |
| 3 | POST | `/api/subscription/verify` | Verify payment after Razorpay modal closes | Yes |
| 4 | GET | `/api/subscription/history` | List past payments | Yes |
| 5 | POST | `/api/webhooks/razorpay` | Webhook (Razorpay calls this, not FE) | No |

---

## 1. Check Subscription Status

Call this on page load to decide whether to show the paywall.

**Request:**
```bash
curl -X POST http://localhost:8000/api/subscription/status \
  -H "Authorization: Bearer <clerk_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response (no subscription):**
```json
{
  "active": false,
  "planId": null,
  "planName": null,
  "currentPeriodEnd": null,
  "currentPeriodStart": null,
  "status": null
}
```

**Response (active subscription):**
```json
{
  "active": true,
  "planId": "growth",
  "planName": "Growth",
  "currentPeriodEnd": "2026-06-05T07:47:42.000000",
  "currentPeriodStart": "2026-05-05T07:47:42.000000",
  "status": "active"
}
```

**FE Logic:**
```ts
const res = await api.post('/api/subscription/status', {});
if (!res.data.active) {
  showPaywall();
}
```

---

## 2. Create Checkout Session (Start Payment)

Call this when user clicks "Subscribe" or "Upgrade". Returns everything needed for the Razorpay checkout modal.

**Available Plans:**
| planId | Name | Price |
|--------|------|-------|
| `growth` | Growth | Rs 9,999/month |
| `pro` | Professional | Rs 24,999/month |
| `enterprise` | Enterprise | Rs 49,999/month |

**Request:**
```bash
curl -X POST http://localhost:8000/api/subscription/checkout \
  -H "Authorization: Bearer <clerk_token>" \
  -H "Content-Type: application/json" \
  -d '{"planId": "growth"}'
```

**Response:**
```json
{
  "orderId": "order_PqR1234567890",
  "amount": 999900,
  "currency": "INR",
  "keyId": "rzp_test_xxxxxxxxxxxx",
  "planId": "growth",
  "planName": "Growth",
  "receipt": "rcpt_uuid_abc12345",
  "prefill": {
    "name": "Ashish Yadav",
    "email": "ashish@example.com",
    "contact": "+91 98765 43210"
  }
}
```

**FE Logic (React + Razorpay Checkout.js):**
```tsx
// Step 1: Load Razorpay script (do this once in index.html or useEffect)
// <script src="https://checkout.razorpay.com/v1/checkout.js"></script>

// Step 2: Call checkout endpoint
const handleSubscribe = async (planId: string) => {
  const { data } = await api.post('/api/subscription/checkout', { planId });

  const options = {
    key: data.keyId,
    amount: data.amount,
    currency: data.currency,
    name: "Dhara AI",
    description: `${data.planName} Plan`,
    order_id: data.orderId,
    prefill: data.prefill,
    handler: async (response: any) => {
      // Step 3: Verify payment on backend
      await verifyPayment(response);
    },
    theme: { color: "#6366F1" },
  };

  const rzp = new (window as any).Razorpay(options);
  rzp.open();
};
```

---

## 3. Verify Payment (After Razorpay Modal Closes)

Called in the `handler` callback of Razorpay checkout. Sends the 3 values Razorpay returns.

**Request:**
```bash
curl -X POST http://localhost:8000/api/subscription/verify \
  -H "Authorization: Bearer <clerk_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "razorpayPaymentId": "pay_PqR1234567890",
    "razorpayOrderId": "order_PqR1234567890",
    "razorpaySignature": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
  }'
```

**Response (success):**
```json
{
  "success": true,
  "message": "Payment verified and subscription activated",
  "subscription": {
    "active": true,
    "planId": "growth",
    "planName": "Growth",
    "currentPeriodEnd": "2026-06-05T07:47:42.000000",
    "currentPeriodStart": "2026-05-05T07:47:42.000000",
    "status": "active"
  }
}
```

**Response (signature mismatch — fraud attempt):**
```json
{
  "detail": "Payment signature verification failed"
}
```

**FE Logic:**
```ts
const verifyPayment = async (razorpayResponse: any) => {
  try {
    const { data } = await api.post('/api/subscription/verify', {
      razorpayPaymentId: razorpayResponse.razorpay_payment_id,
      razorpayOrderId: razorpayResponse.razorpay_order_id,
      razorpaySignature: razorpayResponse.razorpay_signature,
    });

    if (data.success) {
      toast.success("Subscription activated!");
      router.push('/pmc'); // redirect to dashboard
    }
  } catch (err) {
    toast.error("Payment verification failed. Contact support.");
  }
};
```

---

## 4. Payment History

**Request:**
```bash
curl -X GET "http://localhost:8000/api/subscription/history?page=1&pageSize=10" \
  -H "Authorization: Bearer <clerk_token>"
```

**Response:**
```json
[
  {
    "id": "uuid-here",
    "razorpayOrderId": "order_PqR1234567890",
    "razorpayPaymentId": "pay_PqR1234567890",
    "amountPaise": 999900,
    "currency": "INR",
    "status": "captured",
    "method": "upi",
    "planId": "growth",
    "createdAt": "2026-05-05T07:47:42.000000"
  }
]
```

---

## 5. Webhook (Backend Only — NOT for FE)

Razorpay POSTs to this endpoint automatically when payments are captured/failed. This is configured in the Razorpay Dashboard, not called by frontend.

```
POST /api/webhooks/razorpay
Header: X-Razorpay-Signature: <hmac_sha256>
Body: Raw JSON from Razorpay
```

---

## Complete FE Integration Example

```tsx
// hooks/useSubscription.ts
import { useAuth } from '@clerk/clerk-react';
import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function useSubscription() {
  const { getToken } = useAuth();
  const [subscription, setSubscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const headers = async () => ({
    'Authorization': `Bearer ${await getToken()}`,
    'Content-Type': 'application/json',
  });

  // Check status on mount
  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscription/status`, {
        method: 'POST',
        headers: await headers(),
        body: '{}',
      });
      const data = await res.json();
      setSubscription(data);
    } finally {
      setLoading(false);
    }
  };

  const subscribe = async (planId: string) => {
    // 1. Create order
    const res = await fetch(`${API_BASE}/api/subscription/checkout`, {
      method: 'POST',
      headers: await headers(),
      body: JSON.stringify({ planId }),
    });
    const checkout = await res.json();

    // 2. Open Razorpay modal
    return new Promise((resolve, reject) => {
      const rzp = new (window as any).Razorpay({
        key: checkout.keyId,
        amount: checkout.amount,
        currency: checkout.currency,
        name: 'Dhara AI',
        description: `${checkout.planName} Plan`,
        order_id: checkout.orderId,
        prefill: checkout.prefill,
        handler: async (response: any) => {
          // 3. Verify payment
          const verifyRes = await fetch(`${API_BASE}/api/subscription/verify`, {
            method: 'POST',
            headers: await headers(),
            body: JSON.stringify({
              razorpayPaymentId: response.razorpay_payment_id,
              razorpayOrderId: response.razorpay_order_id,
              razorpaySignature: response.razorpay_signature,
            }),
          });
          const result = await verifyRes.json();
          if (result.success) {
            setSubscription(result.subscription);
            resolve(result);
          } else {
            reject(new Error('Verification failed'));
          }
        },
        theme: { color: '#6366F1' },
      });
      rzp.open();
    });
  };

  return { subscription, loading, subscribe, checkStatus };
}
```

**Usage in component:**
```tsx
function PricingPage() {
  const { subscription, loading, subscribe } = useSubscription();

  if (loading) return <Spinner />;
  if (subscription?.active) return <Redirect to="/pmc" />;

  return (
    <div>
      <PlanCard name="Growth" price="9,999" onSelect={() => subscribe('growth')} />
      <PlanCard name="Pro" price="24,999" onSelect={() => subscribe('pro')} />
      <PlanCard name="Enterprise" price="49,999" onSelect={() => subscribe('enterprise')} />
    </div>
  );
}
```

---

## Testing with Razorpay Test Mode

Use these test credentials in the Razorpay checkout modal:

| Method | Test Value | Result |
|--------|-----------|--------|
| Card (success) | `4111 1111 1111 1111`, Expiry: any future, CVV: any 3 digits | Payment captured |
| Card (failure) | `4111 1111 1111 1234` | Payment failed |
| UPI (success) | `success@razorpay` | Payment captured |
| UPI (failure) | `failure@razorpay` | Payment failed |
| Netbanking | Select any bank, click Success/Failure on test page | Either outcome |

---

*Last updated: 2026-05-05*
