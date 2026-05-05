# Dharai.ai — Frontend API Integration Guide

> **Scope:** Every API endpoint the frontend must call for the **Public Landing Page**, **PMC Portal**, and **Admin Dashboard** flows.
> This is the single source of truth for backend integration. Each entry includes method, URL, auth requirements, request payload/query params, and the full expected response shape.

---

## Table of Contents

1. [Global Conventions](#1-global-conventions)
2. [Authentication (Shared — Clerk OTP)](#2-authentication-shared--clerk-otp)
   - 2.1 Send OTP — Sign In
   - 2.2 Send OTP — Sign Up (PMC)
   - 2.3 Verify OTP
   - 2.4 Get Current Session
   - 2.5 Sign Out
3. [Public / Landing Page APIs](#3-public--landing-page-apis)
   - 3.1 Submit Enquiry ("Talk to Us" Form)
4. [PMC Portal APIs](#4-pmc-portal-apis)
   - 4.1 Role APIs
   - 4.2 PMC Company Profile
   - 4.3 Portfolio Documents
   - 4.4 Societies (CRUD)
   - 4.5 Society Documents
   - 4.6 Feasibility Reports
   - 4.7 Tenders (Open Marketplace)
   - 4.8 Tenders (PMC-authored per Society)
   - 4.9 Deemed Conveyance (DC) Tenders
   - 4.10 Eligible Societies & Interest Sharing
   - 4.11 Team Management
   - 4.12 Dashboard Overview Stats
   - 4.13 Subscription & Payments
5. [Admin Dashboard APIs](#5-admin-dashboard-apis)
   - 5.1 Admin Bootstrap (Parallel Load)
   - 5.2 Broker / Profile Management
   - 5.3 Developer Management
   - 5.4 Developer Success Manager (DSM)
   - 5.5 Organizations
   - 5.6 User Roles
   - 5.7 Listings (Properties & Projects)
   - 5.8 Deals
   - 5.9 Disputes
   - 5.10 Property Assignments
   - 5.11 Platform Settings
   - 5.12 AI-Powered Search & Bulk Operations
6. [Backend Certificate Verification APIs](#6-backend-certificate-verification-apis)
7. [Status & Enum Reference](#7-status--enum-reference)
8. [Error Response Format](#8-error-response-format)

---

## 1. Global Conventions

### Base URLs

| Service | Env Variable | Default |
|---|---|---|
| Main Backend API | `VITE_API_BASE_URL` | `http://localhost:3000/api` |
| Certificate Verification Service | `VITE_VERIFY_API_BASE_URL` | `http://localhost:4000` |

### Authentication Header

All protected endpoints require a Clerk session token:

```
Authorization: Bearer <clerk_session_token>
```

Obtain the token from Clerk's `useAuth()` hook:
```ts
const { getToken } = useAuth();
const token = await getToken();
```

### Content Types

- JSON payloads: `Content-Type: application/json`
- File uploads: `Content-Type: multipart/form-data` (do **not** set manually; let browser set the boundary)

### Response Envelope (JSON endpoints)

```ts
// Success
{ data: T, error: null }

// Failure
{ data: null, error: { message: string, code?: string } }
```

### Role-Based Access

| Role | Token Source | Required For |
|---|---|---|
| Any authenticated user | Clerk session | Read-only PMC endpoints |
| `pmc_admin` | `user_roles` table | All PMC write operations, team management |
| `pmc_report_analyst` | `user_roles` table | Create/update feasibility reports |
| `pmc_tender_manager` | `user_roles` table | Manage tenders & responses |
| `admin` / `master_admin` | `user_roles` table | All admin endpoints |

---

## 2. Authentication (Shared — Clerk OTP)

Authentication is handled via **Clerk's SDK** (not direct HTTP calls). The patterns below show exactly what the frontend calls at each step.

### 2.1 Send OTP — Sign In

**Trigger:** User submits email on the Sign In tab of `/pmc/login` or `/admin/login`.

**Clerk SDK calls:**
```ts
// Step 1 — create sign-in attempt
const signIn = await clerk.client.signIn.create({ identifier: email });

// Step 2 — identify the email address factor ID
const emailFactor = signIn.supportedFirstFactors.find(
  (f) => f.strategy === 'email_code'
);

// Step 3 — send the OTP
await signIn.prepareFirstFactor({
  strategy: 'email_code',
  emailAddressId: emailFactor.emailAddressId,
});
```

**Payload (internal Clerk):** `{ identifier: string }`

**UI State after call:** Advance to OTP input step.

---

### 2.2 Send OTP — Sign Up (PMC)

**Trigger:** User submits the Create Account form on `/pmc/login`.

**Clerk SDK calls:**
```ts
const signUp = await clerk.client.signUp.create({
  emailAddress: email,
  firstName: firstName,
  lastName: lastName,           // optional
  unsafeMetadata: {
    role: "pmc",               // always "pmc" for PMC portal
    company: companyName,      // optional
    phone: phone,              // optional
  },
});

await signUp.prepareEmailAddressVerification({ strategy: 'email_code' });
```

**Payload structure (`unsafeMetadata`):**

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | `"pmc"` | Yes | Always `"pmc"` for PMC portal signup |
| `company` | `string` | No | PMC firm name |
| `phone` | `string` | No | Contact phone |

**UI State after call:** Advance to OTP input step.

---

### 2.3 Verify OTP

**Trigger:** User enters the 6-digit code.

**Clerk SDK calls:**

For **sign-in**:
```ts
const result = await signIn.attemptFirstFactor({
  strategy: 'email_code',
  code: otpCode,             // 6-digit string
});
// result.status === 'complete' → session activated
```

For **sign-up**:
```ts
const result = await signUp.attemptEmailAddressVerification({ code: otpCode });
// result.status === 'complete' → session activated
```

**On success (PMC Sign-Up only):** Immediately call the **Assign PMC Role** endpoint (§4.1.1).

**On success (both):** Redirect to `/pmc` (PMC portal) or `/admin` (admin dashboard).

---

### 2.4 Get Current Session

**Purpose:** Check if user is already logged in on page load.

**Clerk SDK call:**
```ts
const { session } = await clerk.client.sessions.getSession();
// session?.user → current user or null
```

**Also available via hook:**
```ts
const { user, isLoaded, isSignedIn } = useUser(); // from @clerk/clerk-react
```

**Response shape (AuthUser):**
```ts
{
  id: string;               // Clerk user ID
  email: string;
  created_at: string;
  user_metadata: {
    full_name?: string;
    user_type?: string;
    company_name?: string;
    country?: string;
  };
}
```

---

### 2.5 Sign Out

**Clerk SDK call:**
```ts
await clerk.signOut();
// Redirects to '/' or specified returnUrl
```

---

## 3. Public / Landing Page APIs

These endpoints back the public marketing landing page (`src/pages/Index.tsx`) and **do not require authentication**. They are reachable from a fresh, unauthenticated browser.

Base path prefix: `/api/public`

---

### 3.1 Submit Enquiry ("Talk to Us" Form)

**Purpose:** Capture lead details from the landing-page **"Talk to Us"** dialog (`src/components/EnquiryDialog.tsx`), opened by the hero CTA `<Phone /> Talk to Us` and surfaced anywhere `<EnquiryDialog>` wraps a button. Persists the enquiry and triggers the internal sales notification (email/Slack/CRM) so the team can follow up within 24 hours.

**Method:** `POST`
**Endpoint:** `POST /api/public/enquiries`

**Auth Required:** None (public endpoint — no `Authorization` header).

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Rajesh Desai",
  "email": "rajesh@example.com",
  "phone": "+91 98765 43210",
  "user_type": "society",
  "concern": "We are a 48-flat society in Andheri exploring redevelopment. Looking for guidance on PMC selection."
}
```

**Field Specs (must match `EnquiryDialog.tsx` Zod schema):**

| Field | Type | Required | Validation |
|---|---|---|---|
| `name` | `string` | Yes | 2–100 chars |
| `email` | `string` | Yes | Valid email, max 255 chars |
| `phone` | `string` | Yes | 10–15 chars (raw input, may contain `+`, spaces) |
| `user_type` | `enum` | Yes | One of `"society"`, `"builder"`, `"pmc"` |
| `concern` | `string` | No | Free-text, max 500 chars |

**Success Response `201`:**
```json
{
  "data": {
    "id": "enq-uuid-1",
    "name": "Rajesh Desai",
    "email": "rajesh@example.com",
    "phone": "+91 98765 43210",
    "user_type": "society",
    "concern": "We are a 48-flat society in Andheri exploring redevelopment. Looking for guidance on PMC selection.",
    "status": "new",
    "submittedAt": "2026-04-30T10:42:00Z"
  },
  "error": null
}
```

**Validation Error `400`:**
```json
{
  "data": null,
  "error": {
    "message": "Please enter a valid email",
    "code": "VALIDATION_FAILED",
    "details": { "field": "email" }
  }
}
```

**Backend Responsibilities:**
- Persist to an `enquiries` table with `status: "new"`.
- (Optional) Trigger internal notification: email to sales inbox / Slack webhook / CRM lead creation.
- Apply rate-limiting per IP (e.g. max 5 submissions / hour) to prevent spam — return `429` if exceeded.
- Optionally validate phone format (strip non-digits, verify length 10–15).

**Frontend Behavior on Success:**
- Show success state inside the dialog ("Enquiry Submitted! Our team will reach out to you within 24 hours.").
- Toast: `"Enquiry submitted!"` with description `"Our team will contact you within 24 hours."`.
- Auto-close dialog after 2 seconds; reset form.

**Callsite in FE:** `src/components/EnquiryDialog.tsx:64` — replace the mock `setTimeout(1500)` block in `onSubmit` with this POST.

**Auth Required Role:** None (public).

---

## 4. PMC Portal APIs

Base path prefix: `/api/pmc`

Auth required on all PMC endpoints: `Authorization: Bearer <clerk_token>`

---

### 4.1 Role APIs

#### 4.1.1 Assign PMC Role (post-signup)

**Purpose:** Grant `pmc_admin` to a newly created PMC user. Called immediately after OTP sign-up succeeds.

**Method:** `POST`
**Endpoint:** `POST /api/functions/assign-pmc-role`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "role": "pmc_admin"
}
```

**Success Response `200`:**
```json
{
  "success": true
}
```

**Error Response `400/500`:**
```json
{
  "success": false,
  "error": "Role assignment failed"
}
```

**Callsite in FE:** `PMCLogin.tsx:29` — called inside `otp.onSuccess` callback when `mode === 'signup'`.

---

#### 4.1.2 Get PMC Role

**Purpose:** Read the signed-in PMC user's effective role to control UI visibility (which tabs/actions are shown).

**Method:** `POST`
**Endpoint:** `POST /api/rpc/get_pmc_role`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Request Body:** `{}` (empty)

**Success Response `200`:**
```json
"pmc_admin"
```
or
```json
"pmc_report_analyst"
```
or
```json
"pmc_tender_manager"
```
or
```json
null
```

**Callsite in FE:** `src/hooks/usePMCRole.ts:32` — called on every page load when user is signed in.

**Permission mapping (computed in FE from this value):**

| Role | `isAdmin` | `canViewReports` | `canViewTenders` | `canManageTeam` | `canRegisterSociety` |
|---|---|---|---|---|---|
| `pmc_admin` | true | true | true | true | true |
| `pmc_report_analyst` | false | true | false | false | false |
| `pmc_tender_manager` | false | false | true | false | false |
| `null` | false | false | false | false | false |

---

### 4.2 PMC Company Profile

#### 4.2.1 Get PMC Profile

**Purpose:** Load the PMC firm's company details on the Profile tab.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/profile`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:** None

**Success Response `200`:**
```json
{
  "data": {
    "companyName": "Redevelop Pro Pvt. Ltd.",
    "registrationNumber": "PMC-MH-2021-0042",
    "website": "https://redeveloppro.com",
    "phone": "+91 98765 43210",
    "email": "contact@redeveloppro.com",
    "address": "304, Solitaire Business Hub, Andheri West, Mumbai",
    "experience": "12 years",
    "projectsCompleted": "45+",
    "specialization": "Residential Redevelopment",
    "portfolio": "Specializing in cooperative society redevelopment in MMR"
  },
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.2.2 Update PMC Profile

**Purpose:** Save edits made in the Profile tab's Edit form.

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/profile`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body (all fields optional — send only changed fields):**
```json
{
  "companyName": "string",
  "registrationNumber": "string",
  "website": "string",
  "phone": "string",
  "email": "string",
  "address": "string",
  "experience": "string",
  "projectsCompleted": "string",
  "specialization": "string",
  "portfolio": "string"
}
```

**Success Response `200`:**
```json
{
  "data": { /* full updated profile, same shape as GET */ },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.3 Portfolio Documents

#### 4.3.1 List Portfolio Documents

**Purpose:** Show uploaded PDF documents in the Profile → Portfolio Documents card.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/portfolio-documents`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:** None

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "doc-uuid-1",
      "name": "Company Profile 2024.pdf",
      "size": "2.4 MB",
      "uploadedOn": "2024-11-15T09:30:00Z",
      "url": "https://storage.example.com/pmc/docs/company-profile.pdf"
    }
  ],
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.3.2 Upload Portfolio Document

**Purpose:** Upload a new PDF to the Portfolio Documents list.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/portfolio-documents`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `file` | `File` | Yes | PDF only, max 25 MB |
| `name` | `string` | No | Display name (defaults to filename) |

**Success Response `201`:**
```json
{
  "data": {
    "id": "doc-uuid-new",
    "name": "Company Profile 2024.pdf",
    "size": "2.4 MB",
    "uploadedOn": "2024-11-15T09:30:00Z",
    "url": "https://storage.example.com/pmc/docs/company-profile.pdf"
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.3.3 Delete Portfolio Document

**Purpose:** Remove a document from the portfolio list.

**Method:** `DELETE`
**Endpoint:** `DELETE /api/pmc/portfolio-documents/:id`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `id` | `string` | Document UUID |

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{ "data": null, "error": null }
```

**Auth Required Role:** `pmc_admin`

---

#### 4.3.4 Download Portfolio Document

**Purpose:** Fetch signed/direct download URL for a portfolio document.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/portfolio-documents/:id/download`

**Success Response:** `302 Redirect` to signed storage URL, or:
```json
{ "data": { "downloadUrl": "https://..." }, "error": null }
```

---

### 4.4 Societies (Managed)

#### 4.4.1 List Managed Societies

**Purpose:** Show all societies the PMC firm is managing (main `PMCSocieties` page and `PMCDashboard` society list).

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `search` | `string` | No | Filter by society name or location |
| `status` | `string` | No | Filter by `SocietyStatus` value (see §7) |
| `page` | `number` | No | Page number, 1-indexed (default: 1) |
| `pageSize` | `number` | No | Items per page (default: 20) |

**Success Response `200`:**
```json
{
  "data": {
    "items": [
      {
        "id": "soc-uuid-1",
        "name": "Shanti Nagar CHS",
        "location": "Andheri West, Mumbai",
        "registrationNumber": "MH-MBR-CHS-12345",
        "totalFlats": 48,
        "yearBuilt": 1987,
        "contactPerson": "Ramesh Patil",
        "contactPhone": "+91 98700 00001",
        "status": "report_draft",
        "reports": 2,
        "tenders": 0,
        "registeredOn": "2024-01-10T00:00:00Z",
        "notes": "Committee meeting scheduled for Jan 20"
      }
    ],
    "total": 12,
    "page": 1,
    "pageSize": 20
  },
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.4.2 Get Society By ID

**Purpose:** Load a single society's data for the `PMCSocietyDetail` page.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies/:id`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `id` | `string` | Society UUID |

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": {
    "id": "soc-uuid-1",
    "name": "Shanti Nagar CHS",
    "location": "Andheri West, Mumbai",
    "registrationNumber": "MH-MBR-CHS-12345",
    "totalFlats": 48,
    "yearBuilt": 1987,
    "contactPerson": "Ramesh Patil",
    "contactPhone": "+91 98700 00001",
    "status": "report_approved",
    "reports": 2,
    "tenders": 0,
    "registeredOn": "2024-01-10T00:00:00Z",
    "notes": "Committee meeting scheduled for Jan 20",
    "isManualProcess": false
  },
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.4.3 Register Society

**Purpose:** Submit the Register Society form at `/pmc/societies/register`.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/societies`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Shanti Nagar CHS",
  "location": "Andheri West, Mumbai",
  "initialStatus": "new",
  "onboardedDate": 1704844800000,
  "pointOfContact": [
    {
      "contactPerson": "Ramesh Patil",
      "contactMail": "ramesh@example.com",
      "contactPhone": "+91 98700 00001"
    }
  ],
  "notes": "Initial outreach done"
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `string` | Yes | Society name |
| `location` | `string` | Yes | Full address |
| `initialStatus` | `SocietyStatus` | Yes | See §7 |
| `onboardedDate` | `number` | Yes | Unix timestamp (ms) |
| `pointOfContact` | `array` | Yes | At least one contact |
| `notes` | `string` | No | Internal notes |

**Success Response `201`:**
```json
{
  "data": { /* created society object, same shape as 3.4.2 */ },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.4.4 Update Society

**Purpose:** Update society notes, status, or manual-process flag. Used from the Society Detail page.

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/societies/:id`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body (all fields optional — send only what changed):**
```json
{
  "notes": "Updated committee notes",
  "status": "tender_draft",
  "isManualProcess": false
}
```

**Success Response `200`:**
```json
{
  "data": { /* updated society object */ },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.5 Society Documents

#### 4.5.1 List Society Documents

**Purpose:** Populate the Documents tab on the `PMCSocietyDetail` page.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies/:societyId/documents`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `societyId` | `string` | Society UUID |

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "doc-uuid-1",
      "name": "Society Registration Certificate.pdf",
      "type": "pdf",
      "size": "1.2 MB",
      "uploadedBy": "Suresh Mehta",
      "uploadedOn": "2024-02-01T10:00:00Z",
      "url": "https://storage.example.com/society-docs/..."
    }
  ],
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.5.2 Upload Society Document

**Purpose:** Upload a document to a specific society.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/societies/:societyId/documents`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `file` | `File` | Yes | PDF/JPG/PNG, max 25 MB |
| `name` | `string` | Yes | Document display name |

**Success Response `201`:**
```json
{
  "data": { /* created document record, same shape as list item */ },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.5.3 Delete Society Document

**Method:** `DELETE`
**Endpoint:** `DELETE /api/pmc/societies/:societyId/documents/:docId`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{ "data": null, "error": null }
```

**Auth Required Role:** `pmc_admin`

---

#### 4.5.4 Download Society Document

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies/:societyId/documents/:docId/download`

**Success Response:** `302 Redirect` to signed URL, or `{ "data": { "downloadUrl": "..." } }`

---

### 4.6 Feasibility Reports

#### 4.6.1 List All Reports (PMC-wide)

**Purpose:** Show reports list in the Dashboard Reports tab.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/reports`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `societyId` | `string` | No | Filter to reports for a specific society |
| `status` | `string` | No | Filter by report status (see §7) |

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "rep-uuid-1",
      "society": "Shanti Nagar CHS",
      "societyId": "soc-uuid-1",
      "status": "draft",
      "feasibility": "pending",
      "createdAt": "2024-03-10T11:00:00Z",
      "fsi": 2.5,
      "estimatedValue": "₹210 Cr",
      "plotArea": 2800,
      "existingUnits": 48,
      "proposedUnits": 96,
      "structuralGrade": "C2",
      "completionDays": 730,
      "aiSummary": "Positive feasibility with 2x unit increase potential"
    }
  ],
  "error": null
}
```

**Auth Required Role:** Any PMC role (`pmc_admin` or `pmc_report_analyst`)

---

#### 4.6.2 List Reports for a Society

**Purpose:** Show reports in the Reports tab of `PMCSocietyDetail`.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies/:societyId/reports`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `societyId` | `string` | Society UUID |

**Success Response `200`:** Same shape as §4.6.1

**Auth Required Role:** Any PMC role

---

#### 4.6.3 Create Feasibility Report

**Purpose:** Submit the Create Feasibility Report modal form. Contains file uploads so must be `multipart/form-data`.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/societies/:societyId/reports`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `skipped` | `boolean` | Yes | If true, skip land data entry |
| `landIdentifierType` | `"CTS" \| "FP"` | Yes | Land parcel type |
| `landIdentifierValue` | `string` | Yes | CTS or FP number |
| `oldPlan` | `File` | No | PDF/DWG/DXF/PNG/JPG, max 25 MB |
| `tenementMode` | `"upload" \| "manual"` | Yes | How tenement count is provided |
| `tenementsSheet` | `File` | No | CSV/XLSX/PDF, required if `tenementMode=upload` |
| `numberOfTenements` | `number` | No | Required if `tenementMode=manual` |
| `numberOfCommercialShops` | `number` | No | |
| `basementRequired` | `"yes" \| "no"` | No | |
| `corpusCommercial` | `number` | No | |
| `corpusResidential` | `number` | No | |
| `bankGuranteeCommercial` | `number` | No | |
| `bankGuranteeResidential` | `number` | No | |
| `saleCommercialMunBuaSqFt` | `number` | No | |
| `commercialAreaCostPerSqFt` | `number` | No | |
| `residentialAreaCostPerSqFt` | `number` | No | |
| `podiumParkingCostPerSqFt` | `number` | No | |
| `basementCostPerSqFt` | `number` | No | |
| `costAcquisition79a` | `number` | No | |
| `saleAreaBreakup[groundFloor][area]` | `number` | No | Multipart nested field |
| `saleAreaBreakup[groundFloor][rate]` | `number` | No | |
| `saleAreaBreakup[firstFloor][area]` | `number` | No | |
| `saleAreaBreakup[firstFloor][rate]` | `number` | No | |
| `saleAreaBreakup[secondFloor][area]` | `number` | No | |
| `saleAreaBreakup[secondFloor][rate]` | `number` | No | |
| `saleAreaBreakup[otherFloors][area]` | `number` | No | |
| `saleAreaBreakup[otherFloors][rate]` | `number` | No | |
| `salableResidentialRatePerSqFt` | `number` | No | |
| `carsToSellRatePerCar` | `number` | No | |

**Success Response `201`:**
```json
{
  "data": {
    "id": "rep-uuid-new",
    "societyId": "soc-uuid-1",
    "status": "draft",
    "feasibility": "pending",
    "createdAt": "2024-03-10T11:00:00Z"
    /* ...full report shape... */
  },
  "error": null
}
```

**UI after success:** Navigate to `/pmc/societies/:id/report/:reportId`

**Auth Required Role:** `pmc_admin` or `pmc_report_analyst`

---

#### 4.6.4 Get Report By ID

**Purpose:** Load a single report for editing/viewing in `PMCReportEditor`.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/reports/:reportId`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:** Same shape as a single item from §4.6.1

**Auth Required Role:** Any PMC role

---

#### 4.6.5 Update / Save Report Draft

**Purpose:** Save partial field edits from `PMCReportEditor`.

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/reports/:reportId`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:** Any subset of the report fields:
```json
{
  "fsi": 2.5,
  "estimatedValue": "₹210 Cr",
  "structuralGrade": "C2",
  "feasibility": "positive",
  "aiSummary": "Feasibility looks good"
}
```

**Success Response `200`:** Updated report object

**Auth Required Role:** `pmc_report_analyst` or `pmc_admin`

---

#### 4.6.6 Finalize / Publish Report

**Purpose:** Transition report from `draft → final`. Also flips society status from `report_draft` to `report_approved`.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/reports/:reportId/finalize`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Request Body:** `{}` (empty)

**Success Response `200`:**
```json
{
  "data": { /* updated report with status: "final" */ },
  "error": null
}
```

**Auth Required Role:** `pmc_report_analyst` or `pmc_admin`

---

### 4.7 Tenders (Open Marketplace)

#### 4.7.1 List Open Tenders

**Purpose:** Show available society tenders in the PMC Dashboard "Explore" / Tenders tab.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/open-tenders`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `search` | `string` | No | Filter by society name or location |
| `type` | `"pmc" \| "deemed_conveyance"` | No | Tender type filter |
| `page` | `number` | No | Default: 1 |
| `pageSize` | `number` | No | Default: 20 |

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "tender-uuid-1",
      "society": "Shanti Nagar CHS",
      "location": "Andheri West, Mumbai",
      "type": "pmc",
      "units": 48,
      "plotArea": 2800,
      "yearBuilt": 1987,
      "aiScore": 87,
      "services": ["Feasibility Report", "Tender Management", "Builder Coordination"],
      "deadline": "2025-02-28T23:59:59Z",
      "status": "open",
      "description": "Society seeking PMC for complete redevelopment",
      "contactPerson": "Ramesh Patil",
      "contactPhone": "+91 98700 00001",
      "totalMembers": 48,
      "registrationNo": "MH-MBR-CHS-12345",
      "yearEstablished": "1987"
    }
  ],
  "error": null
}
```

**Auth Required Role:** Any PMC role

---

#### 4.7.2 Submit Tender Proposal

**Purpose:** PMC firm submits a bid/proposal for an open tender.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/open-tenders/:tenderId/proposals`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `tenderId` | `string` | Open tender UUID |

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "fee": "18",
  "services": ["Feasibility Report", "Tender Management", "Builder Coordination"],
  "message": "We have 12 years of experience in MMR region redevelopments..."
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `fee` | `string` | Yes | Proposed fee in Lakhs (numeric string) |
| `services` | `string[]` | Yes | List of services being offered |
| `message` | `string` | Yes | Min 20 characters |

**Success Response `201`:**
```json
{
  "data": {
    "id": "proposal-uuid-1",
    "tenderId": "tender-uuid-1",
    "tenderTitle": "PMC Required — Shanti Nagar CHS",
    "society": "Shanti Nagar CHS",
    "location": "Andheri West, Mumbai",
    "submittedOn": "2024-11-20T10:00:00Z",
    "status": "under_review",
    "proposedFee": "₹18 Lakhs",
    "services": ["Feasibility Report", "Tender Management"],
    "deadline": "2025-02-28T23:59:59Z",
    "competitorCount": 3,
    "aiRank": 2,
    "proposalMessage": "We have 12 years..."
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.7.3 List My Submitted Tenders (Proposals)

**Purpose:** Show tenders the PMC firm has bid on, with status tracking and LOI details.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/submitted-tenders`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `status` | `string` | No | Filter by proposal status (see §7) |

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "proposal-uuid-1",
      "tenderTitle": "PMC Required — Shanti Nagar CHS",
      "society": "Shanti Nagar CHS",
      "location": "Andheri West, Mumbai",
      "submittedOn": "2024-11-20T10:00:00Z",
      "status": "won",
      "proposedFee": "₹18 Lakhs",
      "services": ["Feasibility Report", "Tender Management"],
      "deadline": "2025-02-28T23:59:59Z",
      "competitorCount": 3,
      "aiRank": 1,
      "proposalMessage": "We have 12 years...",
      "loi": {
        "generatedOn": "2025-01-05T00:00:00Z",
        "society": "Shanti Nagar CHS",
        "fee": "₹18 Lakhs",
        "scope": "Full redevelopment PMC services",
        "startDate": "2025-02-01T00:00:00Z",
        "duration": "36 months"
      }
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.8 Tenders (PMC-authored per Society)

#### 4.8.1 List Society Tenders

**Purpose:** Show tenders created by PMC for a specific society (in the Tenders tab of `PMCSocietyDetail`).

**Method:** `GET`
**Endpoint:** `GET /api/pmc/societies/:societyId/tenders`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "tender-uuid-1",
      "title": "Redevelopment Tender — Shanti Nagar CHS",
      "description": "Looking for experienced builder...",
      "scope": "Full redevelopment\nBasement parking\nClub house",
      "deadline": "2025-03-31T23:59:59Z",
      "status": "active",
      "estimatedValue": "₹85 Cr",
      "createdAt": "2024-12-01T00:00:00Z",
      "responsesCount": 5
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin` or `pmc_tender_manager`

---

#### 4.8.2 Create Society Tender

**Purpose:** Publish a redevelopment tender for builder bids (after report is finalized).

**Method:** `POST`
**Endpoint:** `POST /api/pmc/societies/:societyId/tenders`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Redevelopment Tender — Shanti Nagar CHS",
  "description": "Cooperative housing society of 48 flats seeking qualified builder...",
  "scope": "Full redevelopment\nBasement parking\nClub house",
  "deadline": "2025-03-31T23:59:59Z",
  "estimatedValue": "₹85 Cr"
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | `string` | Yes | Tender title |
| `description` | `string` | Yes | Detailed description |
| `scope` | `string` | Yes | Newline-separated scope items |
| `deadline` | `string` | Yes | Future ISO date |
| `estimatedValue` | `string` | No | e.g. "₹85 Cr" |

**Success Response `201`:** Created tender object. Also transitions society status to `tender_live` (use `tender_draft` if the tender is saved without publishing).

**Auth Required Role:** `pmc_admin`

---

#### 4.8.3 List Tender Responses / Bids

**Purpose:** View all builder bids received for a society tender.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/tenders/:tenderId/responses`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "bid-uuid-1",
      "bidderId": "builder-uuid-1",
      "bidderName": "Omkar Realtors",
      "proposedCost": "₹82 Cr",
      "timeline": "30 months",
      "submittedOn": "2025-01-10T00:00:00Z",
      "status": "under_review",
      "message": "We have completed 20+ similar projects..."
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin` or `pmc_tender_manager`

---

#### 4.8.4 Finalize Tender Winner / Issue LOI

**Purpose:** Select winning builder and generate LOI.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/tenders/:tenderId/finalize`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "winningBidderId": "builder-uuid-1"
}
```

**Success Response `200`:** Updated tender with `status: "closed"`, society transitions to `builder_selected`.

**Auth Required Role:** `pmc_admin`

---

### 4.9 Deemed Conveyance (DC) Tenders

#### 4.9.1 Create DC Tender

**Purpose:** Publish a Deemed Conveyance tender for lawyer selection.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/societies/:societyId/dc-tenders`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Deemed Conveyance — Shanti Nagar CHS",
  "description": "Society requires legal assistance for deemed conveyance process",
  "scope": "Documentation review\nCourt representation\nRegistration",
  "deadline": "2025-04-30T23:59:59Z"
}
```

**Success Response `201`:**
```json
{
  "data": {
    "id": "dc-tender-uuid-1",
    "societyId": "soc-uuid-1",
    "title": "Deemed Conveyance — Shanti Nagar CHS",
    "description": "...",
    "scope": "...",
    "deadline": "2025-04-30T23:59:59Z",
    "status": "draft",
    "createdAt": "2024-12-15T00:00:00Z"
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.9.2 Update DC Tender Status

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/dc-tenders/:dcTenderId`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "status": "active"
}
```

**Allowed status values:** `"draft"` | `"active"` | `"review_pending"` | `"closed"`

**Success Response `200`:** Updated DC tender object

**Auth Required Role:** `pmc_admin`

---

#### 4.9.3 Finalize DC Bidder (Select Lawyer)

**Method:** `POST`
**Endpoint:** `POST /api/pmc/dc-tenders/:dcTenderId/finalize`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "lawyerName": "Adv. Suresh Kumar",
  "firmName": "Kumar & Associates"
}
```

**Success Response `200`:**
```json
{
  "data": {
    "id": "dc-tender-uuid-1",
    "status": "closed",
    "selectedBidder": "Adv. Suresh Kumar",
    "loiGenerated": true
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.10 Eligible Societies & Interest Sharing

#### 4.10.1 List Eligible Societies

**Purpose:** Browse AI-recommended societies for PMC outreach (Explore tab).

**Method:** `GET`
**Endpoint:** `GET /api/pmc/eligible-societies`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `search` | `string` | No | Filter by name or location |
| `page` | `number` | No | Default: 1 |
| `pageSize` | `number` | No | Default: 20 |

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "elig-soc-uuid-1",
      "name": "Laxmi Heights CHS",
      "location": "Borivali East, Mumbai",
      "units": 72,
      "plotArea": 4200,
      "yearBuilt": 1982,
      "fsi": 2.5,
      "structuralGrade": "C3",
      "estimatedValue": "₹310 Cr",
      "aiScore": 91,
      "eligibilityReason": "Old structure, high FSI potential, willing committee",
      "contactPerson": "Vijay Sharma",
      "totalMembers": 72,
      "registrationNo": "MH-MBR-CHS-67890"
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.10.2 Share Interest with Eligible Society

**Purpose:** PMC expresses interest in an eligible society (sends proposal summary).

**Method:** `POST`
**Endpoint:** `POST /api/pmc/shared-interests`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "societyId": "elig-soc-uuid-1",
  "fee": "20",
  "message": "We are interested in managing your redevelopment project. Our team has..."
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `societyId` | `string` | Yes | Eligible society UUID |
| `fee` | `string` | Yes | Proposed fee in Lakhs |
| `message` | `string` | Yes | Min 20 characters |

**Success Response `201`:** Created shared interest record (see §4.10.3)

**Auth Required Role:** `pmc_admin`

---

#### 4.10.3 List My Shared Interests

**Method:** `GET`
**Endpoint:** `GET /api/pmc/shared-interests`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "interest-uuid-1",
      "society": "Laxmi Heights CHS",
      "location": "Borivali East, Mumbai",
      "sharedOn": "2024-11-18T00:00:00Z",
      "status": "proposal_sent",
      "proposalSummary": "₹20 Lakhs management fee",
      "responseStatus": "Awaiting committee response",
      "units": 72,
      "plotArea": 4200,
      "contactPerson": "Vijay Sharma"
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.11 Team Management

#### 4.11.1 List Team Members

**Purpose:** Show all team members of the PMC firm on the Team tab.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/team`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "member-uuid-1",
      "name": "Priya Desai",
      "email": "priya@dhara.ai",
      "roles": ["pmc_report_analyst"],
      "status": "active",
      "enabled": true
    }
  ],
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.11.2 Invite Team Member

**Purpose:** Send invitation email to a new team member.

**Method:** `POST`
**Endpoint:** `POST /api/pmc/team/invitations`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Priya Desai",
  "email": "priya@dhara.ai",
  "role": "pmc_report_analyst"
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `string` | No | Min 3 chars if provided |
| `email` | `string` | Yes | Must end with `@dhara.ai` |
| `role` | `string` | Yes | One of: `pmc_admin`, `pmc_report_analyst`, `pmc_tender_manager` |

**Success Response `201`:**
```json
{
  "data": {
    "id": "member-uuid-new",
    "name": "Priya Desai",
    "email": "priya@dhara.ai",
    "roles": ["pmc_report_analyst"],
    "status": "pending",
    "enabled": true
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

#### 4.11.3 Update Team Member Roles

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/team/:memberId/roles`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "roles": ["pmc_report_analyst", "pmc_tender_manager"]
}
```

**Success Response `200`:** Updated member object

**Auth Required Role:** `pmc_admin`

---

#### 4.11.4 Enable / Disable Team Member

**Method:** `PATCH`
**Endpoint:** `PATCH /api/pmc/team/:memberId`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "enabled": false
}
```

**Success Response `200`:** Updated member object

**Auth Required Role:** `pmc_admin`

---

#### 4.11.5 Resend Invitation

**Method:** `POST`
**Endpoint:** `POST /api/pmc/team/invitations/:invitationId/resend`

**Success Response `200`:** `{ "data": { "success": true }, "error": null }`

**Auth Required Role:** `pmc_admin`

---

#### 4.11.6 Revoke Invitation

**Method:** `DELETE`
**Endpoint:** `DELETE /api/pmc/team/invitations/:invitationId`

**Success Response `200`:** `{ "data": null, "error": null }`

**Auth Required Role:** `pmc_admin`

---

### 4.12 Dashboard Overview Stats

#### 4.12.1 Get Overview Summary

**Purpose:** Populate the Overview tab cards and charts on `PMCDashboard`.

**Method:** `GET`
**Endpoint:** `GET /api/pmc/overview`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Query Params:** None

**Success Response `200`:**
```json
{
  "data": {
    "metrics": {
      "totalSocieties": 12,
      "newSocietiesThisMonth": 2,
      "avgDaysToBuilderSelection": 94,
      "societiesCompleted": 3,
      "feasibilityReports": 18,
      "pendingReview": 4,
      "teamMembers": 5,
      "unassigned": 1
    },
    "societyStatusBreakdown": [
      { "key": "new", "label": "New", "count": 2 },
      { "key": "report_draft", "label": "Report Draft", "count": 2 },
      { "key": "report_approved", "label": "Report Approved", "count": 2 },
      { "key": "tender_draft", "label": "Tender Draft", "count": 1 },
      { "key": "tender_live", "label": "Tender Live", "count": 3 },
      { "key": "tender_review_pending", "label": "Tender Review Pending", "count": 1 },
      { "key": "builder_selected", "label": "Builder Selected", "count": 3 }
    ],
    "teamRoleBreakdown": [
      { "key": "pmc_admin", "label": "PMC Admin", "count": 1 },
      { "key": "pmc_report_analyst", "label": "Report Analyst", "count": 2 },
      { "key": "pmc_tender_manager", "label": "Tender Manager", "count": 2 }
    ],
    "recentActivity": [
      {
        "id": "activity-1",
        "type": "report_created",
        "title": "Feasibility report created",
        "subject": "Shanti Nagar CHS",
        "author": "Priya Desai",
        "timeAgo": "2 hours ago"
      }
    ]
  },
  "error": null
}
```

**Auth Required Role:** `pmc_admin`

---

### 4.13 Subscription & Payments

#### 4.13.1 Get PMC Subscription Status

**Purpose:** Check if the PMC firm has an active subscription (controls paywall visibility).

**Method:** `POST`
**Endpoint:** `POST /api/functions/pmc-subscription-status`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:** `{}` (empty)

**Success Response `200`:**
```json
{
  "data": {
    "active": true,
    "planId": "growth",
    "currentPeriodEnd": "2025-04-01T00:00:00Z"
  },
  "error": null
}
```

When not subscribed:
```json
{
  "data": {
    "active": false,
    "planId": null,
    "currentPeriodEnd": null
  },
  "error": null
}
```

---

#### 4.13.2 Create Checkout Session

**Purpose:** Initiate payment checkout for a subscription plan.

**Method:** `POST`
**Endpoint:** `POST /api/functions/pmc-checkout-session`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "planId": "growth"
}
```

**Success Response `200`:**
```json
{
  "data": {
    "sessionId": "sess_abc123",
    "checkoutUrl": "https://payments.razorpay.com/dharai/checkout?plan=growth"
  },
  "error": null
}
```

**UI after success:** Redirect to `checkoutUrl`.

---

## 5. Admin Dashboard APIs

Base path prefix: `/api/admin` (or direct table access via `/api/db/:table`)

All admin endpoints require: `Authorization: Bearer <clerk_token>` **and** the caller must have an admin role in `user_roles`.

**Admin roles:**
- `master_admin` — full access
- `project_admin` — developer & project management
- `broker_admin` — broker & organization management
- `listing_admin` — property/project listings
- `account_manager` — user accounts
- `individual_success_manager` — individual broker management
- `developer_success_manager` — developer account assignments

---

### 5.1 Admin Bootstrap (Parallel Load)

These 10 requests are fired **in parallel** on admin page mount (`useAdminData.ts:140-151`). All are `GET` requests.

| # | Method | Endpoint | Table | Ordering |
|---|---|---|---|---|
| 1 | GET | `/api/db/profiles` | `profiles` | `created_at DESC` |
| 2 | GET | `/api/db/properties` | `properties` | `created_at DESC` |
| 3 | GET | `/api/db/projects` | `projects` | `created_at DESC` |
| 4 | GET | `/api/db/developers` | `developers` | `name ASC` |
| 5 | GET | `/api/db/developer_requests` | `developer_requests` | `created_at DESC` |
| 6 | GET | `/api/db/organizations?type=broker` | `organizations` | `created_at DESC` |
| 7 | GET | `/api/db/user_roles` | `user_roles` | `created_at DESC` |
| 8 | GET | `/api/db/deals` | `deals` | `created_at DESC` |
| 9 | GET | `/api/db/disputes` | `disputes` | `created_at DESC` |
| 10 | GET | `/api/db/platform_settings` | `platform_settings` | — |

Plus 3 additional queries for DSM mapping:
```
GET /api/db/user_roles?role=developer_success_manager
GET /api/db/profiles?fields=id,user_id,full_name&user_id[in]=<dsm_user_ids>
GET /api/db/organizations?type=developer&developer_id[not_null]=true&fields=developer_id,developer_success_manager_id
```

**Response for each:** `{ "data": [...], "error": null }`

---

### 5.2 Broker / Profile Management

#### 5.2.1 Verify Broker Profile

**Purpose:** Approve a pending broker's profile.

**Method:** `POST`
**Endpoint:** `POST /api/functions/verify-broker`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "profileId": "profile-uuid-1",
  "action": "verify"
}
```

**Success Response `200`:**
```json
{
  "data": { "success": true, "message": "Broker verified successfully" },
  "error": null
}
```

**Auth Required Role:** `admin`, `master_admin`, `broker_admin`, `account_manager`, or `individual_success_manager`

---

#### 5.2.2 Reject Broker Profile

**Method:** `POST`
**Endpoint:** `POST /api/functions/verify-broker`

**Request Body:**
```json
{
  "profileId": "profile-uuid-1",
  "action": "reject",
  "reason": "Incomplete documentation provided"
}
```

**Success Response `200`:**
```json
{
  "data": { "success": true, "message": "Broker rejected" },
  "error": null
}
```

**Auth Required Role:** Same as 4.2.1

---

#### 5.2.3 Create Broker User

**Purpose:** Admin creates a new broker account (bypasses self-signup flow).

**Method:** `POST`
**Endpoint:** `POST /api/functions/create-broker`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "broker@example.com",
  "password": "optional_initial_password",
  "full_name": "Rajesh Kumar",
  "phone": "+91 98765 43210",
  "country": "India",
  "city": "Mumbai",
  "company_name": "Kumar Realty",
  "specialization": "Residential",
  "years_experience": 8,
  "bio": "Senior broker with 8 years in Mumbai market",
  "auto_verify": true,
  "user_type": "broker",
  "organization_id": "org-uuid-1",
  "roles": ["broker_admin"]
}
```

**Field Constraints:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | `string` | Yes | Must be unique |
| `password` | `string` | No | If omitted, user sets password via email |
| `full_name` | `string` | Yes | |
| `phone` | `string` | No | |
| `country` | `string` | No | |
| `city` | `string` | No | |
| `company_name` | `string` | No | |
| `specialization` | `string` | No | |
| `years_experience` | `number` | No | |
| `bio` | `string` | No | |
| `auto_verify` | `boolean` | No | If `true`, sets `verification_status: 'verified'` |
| `user_type` | `string` | No | `broker` / `developer` / `individual` / `internal` |
| `organization_id` | `string` | No | Associate with existing org |
| `roles` | `string[]` | No | Platform roles to assign |

**Success Response `201`:**
```json
{
  "data": {
    "success": true,
    "user": {
      "id": "user-uuid-new",
      "email": "broker@example.com"
    }
  },
  "error": null
}
```

**Auth Required Role:** `admin`, `master_admin`, `broker_admin`

---

#### 5.2.4 Update Profile (Admin)

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/profiles/:profileId`

**Request Body:** Partial profile fields

**Success Response `200`:** Updated profile object

---

### 5.3 Developer Management

#### 5.3.1 Toggle Developer Active/Inactive

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/developers/:developerId`

**Headers:**
```
Authorization: Bearer <clerk_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "is_active": false
}
```

**Success Response `200`:** Updated developer record

**Auth Required Role:** `admin`, `master_admin`, `project_admin`

---

#### 5.3.2 Approve Developer Request

**Purpose:** Convert a pending developer request into an active developer record.

**Method:** `POST`
**Endpoint:** `POST /api/db/developers`

**Request Body:**
```json
{
  "name": "Omkar Realtors",
  "country": "India",
  "city": "Mumbai",
  "website": "https://omkarrealtors.com",
  "description": "Premium developer in MMR region",
  "is_active": true
}
```

**Also:** Update the developer request status:

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/developer_requests/:requestId`

**Request Body:**
```json
{
  "status": "approved"
}
```

**Auth Required Role:** `admin`, `master_admin`, `project_admin`

---

#### 5.3.3 Reject Developer Request

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/developer_requests/:requestId`

**Request Body:**
```json
{
  "status": "rejected",
  "rejection_reason": "Insufficient RERA registration details"
}
```

**Success Response `200`:** Updated developer request

**Auth Required Role:** `admin`, `master_admin`, `project_admin`

---

### 5.4 Developer Success Manager (DSM)

#### 5.4.1 Assign / Unassign DSM to Developer

**Purpose:** Link a DSM user to a developer organization.

**Step 1:** Find org for developer:

**Method:** `GET`
**Endpoint:** `GET /api/db/organizations?developer_id=:developerId&fields=id`

**Step 2:** Update DSM assignment:

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/organizations/:orgId`

**Request Body:**
```json
{
  "developer_success_manager_id": "dsm-user-uuid"
}
```

To unassign:
```json
{
  "developer_success_manager_id": null
}
```

**Auth Required Role:** `admin`, `master_admin`, `developer_success_manager`

---

### 5.5 Organizations

#### 5.5.1 Toggle Broker Organization Active

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/organizations/:orgId`

**Request Body:**
```json
{
  "is_active": false
}
```

**Auth Required Role:** `admin`, `master_admin`, `broker_admin`

---

#### 5.5.2 Create Broker Organization

**Method:** `POST`
**Endpoint:** `POST /api/db/organizations`

**Request Body:**
```json
{
  "name": "Kumar Realty Pvt. Ltd.",
  "type": "broker",
  "city": "Mumbai",
  "country": "India",
  "contact_email": "info@kumarrealty.com",
  "contact_phone": "+91 22 1234 5678",
  "verification_status": "pending",
  "is_active": true
}
```

**Success Response `201`:** Created organization record

**Auth Required Role:** `admin`, `master_admin`, `broker_admin`

---

### 5.6 User Roles

#### 5.6.1 Assign Role

**Purpose:** Grant an admin or platform role to a user.

**Method:** `POST`
**Endpoint:** `POST /api/db/user_roles`

**Request Body:**
```json
{
  "user_id": "user-uuid-1",
  "role": "broker_admin"
}
```

**Available roles:**
`admin`, `master_admin`, `project_admin`, `broker_admin`, `listing_admin`, `account_manager`, `individual_success_manager`, `developer_success_manager`, `pmc_admin`, `pmc_report_analyst`, `pmc_tender_manager`, `sales_executive`, `lawyer`

**Success Response `201`:**
```json
{
  "data": {
    "id": "role-uuid-new",
    "user_id": "user-uuid-1",
    "role": "broker_admin",
    "created_at": "2024-11-20T10:00:00Z"
  },
  "error": null
}
```

**Auth Required Role:** `master_admin`

---

#### 5.6.2 Remove Role

**Method:** `DELETE`
**Endpoint:** `DELETE /api/db/user_roles/:roleId`

**Success Response `200`:** `{ "data": null, "error": null }`

**Auth Required Role:** `master_admin`

---

### 5.7 Listings (Properties & Projects)

#### 5.7.1 Get Properties with Owner Profiles

**Method:** `GET`
**Endpoint:** `GET /api/db/properties?include=owner_profile`

**Query Params:**

| Param | Type | Description |
|---|---|---|
| `listing_approval_status` | `string` | Filter by approval status |
| `order` | `string` | e.g. `created_at:desc` |

**Success Response `200`:**
```json
{
  "data": [
    {
      "id": "prop-uuid-1",
      "title": "3BHK in Bandra West",
      "address": "10, Sea View Society, Bandra West",
      "price": 25000000,
      "beds": 3,
      "baths": 2,
      "area": 1200,
      "description": "Spacious apartment...",
      "owner_id": "profile-uuid-1",
      "listing_approval_status": "pending",
      "created_at": "2024-10-01T00:00:00Z",
      "owner_profile": {
        "id": "profile-uuid-1",
        "full_name": "Rajesh Kumar"
      }
    }
  ],
  "error": null
}
```

---

#### 5.7.2 Create Project (Admin)

**Method:** `POST`
**Endpoint:** `POST /api/functions/admin-create-project`

**Request Body:**
```json
{
  "name": "Omkar Alta Monte",
  "developer_name": "Omkar Realtors",
  "location": "Malad East, Mumbai",
  "price_range_min": 15000000,
  "price_range_max": 35000000,
  "units": 240,
  "description": "Premium luxury high-rise...",
  "website": "https://omkaraltamonte.com"
}
```

**Success Response `201`:**
```json
{
  "data": {
    "project": {
      "id": "proj-uuid-new",
      "name": "Omkar Alta Monte",
      "developer_id": "dev-uuid-1"
    }
  },
  "error": null
}
```

**Auth Required Role:** `admin`, `master_admin`, `project_admin`, `listing_admin`

---

#### 5.7.3 Fetch Project Details

**Method:** `POST`
**Endpoint:** `POST /api/functions/fetch-project-details`

**Request Body:**
```json
{
  "projectId": "proj-uuid-1"
}
```

**Success Response `200`:**
```json
{
  "data": {
    "success": true,
    "data": { /* full project object */ }
  },
  "error": null
}
```

---

### 5.8 Deals

#### 5.8.1 Override Deal Status

**Purpose:** Admin manually overrides the status of a deal with a reason.

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/deals/:dealId`

**Request Body:**
```json
{
  "status": "completed",
  "status_override_by": "admin-user-uuid",
  "status_override_reason": "Manually resolved after dispute settlement"
}
```

**Deal status values:** `pending`, `active`, `completed`, `cancelled`, `disputed`

**Success Response `200`:** Updated deal record

**Auth Required Role:** `admin`, `master_admin`

---

### 5.9 Disputes

#### 5.9.1 Update Dispute Status

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/disputes/:disputeId`

**Request Body:**
```json
{
  "status": "resolved",
  "resolved_by_admin": "admin-user-uuid",
  "resolution_notes": "Both parties agreed to 50-50 commission split"
}
```

**Dispute status values:** `open`, `under_review`, `resolved`, `closed`

**Success Response `200`:** Updated dispute record

**Auth Required Role:** `admin`, `master_admin`

---

### 5.10 Property Assignments

#### 5.10.1 Get My Profile ID (RPC)

**Purpose:** Resolve the admin's own profile ID before creating an assignment record.

**Method:** `POST`
**Endpoint:** `POST /api/rpc/get_my_profile_id`

**Headers:**
```
Authorization: Bearer <clerk_token>
```

**Request Body:** `{}` (empty)

**Success Response `200`:** `{ "data": "profile-uuid-self", "error": null }`

---

#### 5.10.2 Create Property Assignment

**Purpose:** Assign a property to an individual broker/agent.

**Method:** `POST`
**Endpoint:** `POST /api/db/property_assignments`

**Request Body:**
```json
{
  "individual_id": "profile-uuid-individual",
  "property_id": "prop-uuid-1",
  "assigned_by": "profile-uuid-admin"
}
```

**Success Response `201`:**
```json
{
  "data": {
    "id": "assignment-uuid-new",
    "individual_id": "profile-uuid-individual",
    "property_id": "prop-uuid-1",
    "assigned_by": "profile-uuid-admin",
    "created_at": "2024-11-20T10:00:00Z"
  },
  "error": null
}
```

**Auth Required Role:** `admin`, `master_admin`, `individual_success_manager`

---

### 5.11 Platform Settings

#### 5.11.1 Update Platform Setting

**Purpose:** Change a global platform configuration value.

**Method:** `PATCH`
**Endpoint:** `PATCH /api/db/platform_settings/:key`

**Path Params:**

| Param | Type | Description |
|---|---|---|
| `key` | `string` | The setting key (e.g. `commission_rate`) |

**Request Body:**
```json
{
  "value": "2.5"
}
```

**Success Response `200`:** Updated platform setting record

**Auth Required Role:** `master_admin`

---

### 5.12 AI-Powered Search & Bulk Operations

All AI search endpoints use `POST /api/functions/:functionName` pattern.

#### 5.12.1 Search Brokers by City

**Endpoint:** `POST /api/functions/search-brokers-by-city`

**Request Body (choose one):**
```json
{ "city": "Mumbai", "country": "India" }
```
or
```json
{ "sourceUrl": "https://maharera.mahaonline.gov.in/..." }
```

**Success Response `200`:**
```json
{
  "data": {
    "success": true,
    "brokers": [
      {
        "name": "Rajesh Kumar",
        "companyName": "Kumar Realty",
        "reraNumber": "A51900000001",
        "phone": "+91 98765 43210",
        "email": "rajesh@kumarrealty.com",
        "city": "Mumbai",
        "specialization": "Residential",
        "yearsExperience": 8
      }
    ],
    "source": "MahaRERA",
    "reraWebsite": "https://maharera.mahaonline.gov.in"
  },
  "error": null
}
```

---

#### 5.12.2 Search Developers by City

**Endpoint:** `POST /api/functions/search-developers-by-city`

**Request Body:**
```json
{ "city": "Pune", "country": "India" }
```
or
```json
{ "sourceUrl": "https://..." }
```

**Success Response `200`:**
```json
{
  "data": {
    "success": true,
    "developers": [
      {
        "name": "Kolte-Patil Developers",
        "city": "Pune",
        "country": "India",
        "website": "https://koltepatil.com",
        "description": "Leading developer in Pune"
      }
    ],
    "source": "Web scrape"
  },
  "error": null
}
```

---

#### 5.12.3 Search Projects by City

**Endpoint:** `POST /api/functions/search-projects-by-city`

**Request Body:**
```json
{ "city": "Pune", "country": "India" }
```

**Success Response `200`:**
```json
{
  "data": {
    "success": true,
    "projects": [
      {
        "name": "Kolte-Patil Life Republic",
        "developerName": "Kolte-Patil Developers",
        "location": "Hinjewadi, Pune",
        "priceRangeMin": 5000000,
        "priceRangeMax": 12000000,
        "units": 1200,
        "website": "https://liferepublic.koltepatil.com"
      }
    ]
  },
  "error": null
}
```

---

#### 5.12.4 Search Developer's Projects

**Endpoint:** `POST /api/functions/search-developer-projects`

**Request Body:**
```json
{
  "developerName": "Kolte-Patil Developers",
  "city": "Pune",
  "country": "India"
}
```

**Success Response `200`:**
```json
{
  "data": {
    "projects": [ /* array of ProjectSearchResult */ ]
  },
  "error": null
}
```

---

#### 5.12.5 Firecrawl Scrape

**Endpoint:** `POST /api/functions/firecrawl-scrape`

**Request Body:**
```json
{
  "url": "https://koltepatil.com",
  "options": {}
}
```

**Success Response `200`:**
```json
{
  "data": {
    "success": true,
    "markdown": "# Kolte-Patil Developers\n\n...",
    "error": null
  },
  "error": null
}
```

---

#### 5.12.6 Extract Developer Info from Markdown

**Endpoint:** `POST /api/functions/extract-developer-info`

**Request Body:**
```json
{
  "markdown": "# Kolte-Patil Developers\n\n...",
  "url": "https://koltepatil.com",
  "existingDeveloper": { /* optional current developer record to update */ }
}
```

**Success Response `200`:**
```json
{
  "data": {
    "developer": {
      "name": "Kolte-Patil Developers",
      "city": "Pune",
      "country": "India",
      "website": "https://koltepatil.com",
      "description": "Leading real estate developer..."
    }
  },
  "error": null
}
```

---

#### 5.12.7 Extract Projects from Markdown

**Endpoint:** `POST /api/functions/extract-projects-list`

**Request Body:**
```json
{
  "markdown": "...",
  "url": "https://koltepatil.com/projects"
}
```

**Success Response `200`:**
```json
{
  "data": {
    "projects": [ /* array of ProjectSearchResult */ ]
  },
  "error": null
}
```

---

## 6. Backend Certificate Verification APIs

Base URL: `VITE_VERIFY_API_BASE_URL` (default: `http://localhost:4000`)

These APIs are served by the **FastAPI Python backend** (not the main Node backend).

### 6.1 Health Check

**Method:** `GET`
**Endpoint:** `GET /health`

**Auth:** None required

**Success Response `200`:**
```json
{ "ok": true, "service": "dharai-backend" }
```

---

### 6.2 Verify Licensed Surveyor (LS) Certificate

**Purpose:** Verify an uploaded LS certificate against MCGM AutoDCR SOAP database.

**Method:** `POST`
**Endpoint:** `POST /api/verify/license-surveyor`

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `file` | `File` | Yes | PDF, JPG, PNG, WebP. Max 15 MB |

**Process (server-side):**
1. Extract registration number from certificate (OCR if needed — Tesseract)
2. Query MCGM SOAP endpoint with registration number
3. Parse XML response, find matching consultant
4. Validate expiration date

**Success Response `200` (valid):**
```json
{
  "valid": true,
  "expired": false,
  "consultant": {
    "name": "JINISH NARENDRA SONI",
    "registrationNumber": "S/588/LS",
    "validUpto": "31 Mar 2031",
    "firm": null,
    "qualification": null,
    "address": "B-204, Sunrise Tower, Borivali West",
    "city": "MUMBAI",
    "state": "Maharashtra",
    "mobile": "98******30",
    "email": "jinish@example.com"
  },
  "extractedRegistrationNumber": "S/588/LS",
  "usedOcr": true,
  "total": 966
}
```

**Success Response `200` (not found):**
```json
{
  "valid": false,
  "reason": "not_found",
  "message": "No Licensed Surveyor found with registration number S/999/LS",
  "total": 966
}
```

**Error Response `400`:**
```json
{
  "valid": false,
  "reason": "invalid_input",
  "message": "Could not extract registration number from the uploaded file"
}
```

**Error Response `502`:**
```json
{
  "valid": false,
  "reason": "upstream_error",
  "message": "MCGM service unavailable"
}
```

---

### 6.3 Verify Chartered Accountant / Architect (CA) Certificate

**Purpose:** Verify an uploaded CA/Architect certificate against COA (Council of Architecture) portal.

**Method:** `POST`
**Endpoint:** `POST /api/verify/chartered-accountant`

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `file` | `File` | Yes | PDF, JPG, PNG, WebP. Max 15 MB |

**Process (server-side):**
1. Extract registration number from certificate via OCR
2. POST to COA portal (`coa.gov.in/ver_arch.php`)
3. Parse HTML table response
4. Return architect details

**Success Response `200` (valid):**
```json
{
  "valid": true,
  "details": {
    "name": "Mr. HIMANSHU JITENDRA GUJARATHI",
    "registrationNumber": "CA/2024/171364",
    "status": "Active",
    "validUpto": "31/December/2025",
    "city": "Pune",
    "disciplinary": "NO"
  },
  "extractedRegistrationNumber": "CA/2024/171364",
  "usedOcr": true
}
```

**Success Response `200` (not found):**
```json
{
  "valid": false,
  "reason": "not_found",
  "message": "No registered architect found for CA/2024/999999"
}
```

**Error Responses:** Same as §6.2 (`invalid_input` / `upstream_error`)

**Registration Number Formats:**
- Licensed Surveyor: `S/\d+/LS` (e.g. `S/588/LS`)
- Architect/CA: `(CA|AP)/\d+/\d+` (e.g. `CA/2024/171364`)

---

## 7. Status & Enum Reference

### Society Status (`SocietyStatus`)

These are the canonical values backing the **Status filter dropdown** on `PMCSocieties.tsx` and `PMCDashboard.tsx` (society list). The order below matches the lifecycle progression a society moves through.

| Value | Label | Meaning |
|---|---|---|
| `new` | New | Freshly registered, no report or tender yet |
| `report_draft` | Report Draft | Feasibility report is being authored / under manual review |
| `report_approved` | Report Approved | Report finalized, ready to author tender |
| `tender_draft` | Tender Draft | Tender drafted but not yet published |
| `tender_live` | Tender Live | Builder tender is published and accepting bids |
| `tender_review_pending` | Tender Review Pending | Bids received, under review (manual review needed) |
| `builder_selected` | Builder Selected | Winner selected, LOI issued |

### Report Status

| Value | Meaning |
|---|---|
| `draft` | Work in progress |
| `in_progress` | Actively being edited |
| `completed` | Completed but not published |
| `final` | Published/submitted to society |

### Report Feasibility

| Value | Meaning |
|---|---|
| `positive` | Redevelopment is feasible |
| `negative` | Redevelopment not recommended |
| `pending` | Assessment not yet done |

### Tender Status (PMC-authored)

| Value | Meaning |
|---|---|
| `draft` | Not published yet |
| `active` | Open for bids |
| `closed` | Bidding closed |

### Submitted Tender Status (PMC proposals)

| Value | Meaning |
|---|---|
| `under_review` | Proposal received by society |
| `shortlisted` | PMC shortlisted |
| `won` | PMC selected, LOI generated |
| `lost` | Another PMC selected |

### DC Tender Status

| Value | Meaning |
|---|---|
| `draft` | Not yet published |
| `active` | Open for lawyer bids |
| `review_pending` | Bids under review |
| `closed` | Lawyer selected |

### PMC Roles

| Value | Permissions |
|---|---|
| `pmc_admin` | Full access to all PMC features |
| `pmc_report_analyst` | View + create/edit feasibility reports |
| `pmc_tender_manager` | View + manage tenders and responses |

### Admin Roles

| Value | Permissions |
|---|---|
| `master_admin` | Unrestricted platform access |
| `project_admin` | Developer & project management |
| `broker_admin` | Broker & organization management |
| `listing_admin` | Property/project listing approval |
| `account_manager` | User account management |
| `individual_success_manager` | Individual broker management |
| `developer_success_manager` | Developer org assignment |

### Profile `user_type`

`broker` | `developer` | `individual` | `internal`

### Profile `verification_status`

`pending` | `verified` | `rejected`

---

## 8. Error Response Format

### HTTP Status Codes

| Code | When |
|---|---|
| `200` | Success (GET, PATCH, POST returning existing entity) |
| `201` | Created (POST returning new entity) |
| `400` | Bad request (validation failure, missing required field) |
| `401` | Unauthenticated (missing or invalid Clerk token) |
| `403` | Forbidden (authenticated but insufficient role) |
| `404` | Resource not found |
| `422` | Unprocessable entity (correct format but business rule violation) |
| `500` | Internal server error |
| `502` | Upstream service error (MCGM, COA, external APIs) |

### Error Body

```json
{
  "data": null,
  "error": {
    "message": "Human-readable error description",
    "code": "VALIDATION_FAILED",
    "details": { /* optional extra context */ }
  }
}
```

### Function Endpoint Errors

For `/api/functions/*` endpoints:
```json
{
  "data": {
    "success": false,
    "error": "Description of what went wrong"
  },
  "error": null
}
```

---

*Document last updated: 2026-04-30*
*Covers frontend code revision: `ecf17f7` (main branch)*
