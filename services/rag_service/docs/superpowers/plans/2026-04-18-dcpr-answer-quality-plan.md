# DCPR Answer-Quality & Mumbai-Scope Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four session-33 feedback items (scope drift, unit mismatch, missing comparison tables, Pune/UDCPR framing) via prompt + UI-copy edits only. No retrieval changes.

**Architecture:** All edits are localized to `intelligent_rag.py` (rules, defaults, prompts) and `Dhara-frontend/src/app/chat/page.tsx` (UI copy). RAG pipeline, streaming, retrieval, and embeddings are untouched.

**Tech Stack:** Python 3.12, OpenAI client (streaming + non-streaming), Milvus (untouched), Next.js 14 frontend with Tailwind.

**Spec:** `docs/superpowers/specs/2026-04-18-dcpr-answer-quality-design.md`

**Validation strategy:** No unit tests for prompts. Final task replays the six session-33 questions against the updated pipeline and checks behavior against expected outcomes. Each preceding task uses a `grep` sanity check after the edit.

---

## File Structure

| File | Responsibility | Change type |
|------|----------------|-------------|
| `intelligent_rag.py` | LLM prompt templates, query-analysis defaults, answer rules | Rewrite `DCPR_ANSWER_RULES`; flip `"Pune"` defaults; remove UDCPR branch; simplify web queries; rewrite prompt framing |
| `Dhara-frontend/src/app/chat/page.tsx` | Chat UI copy | 4 string updates (footer, placeholder, 2 error fallbacks) |

---

## Task 1: Rewrite `DCPR_ANSWER_RULES`

**Goal:** Replace the current 7-rule block with a new 9-rule block that encodes R1–R4 from the spec plus two concrete negative examples. This is the single most load-bearing change — the three downstream prompts all embed this block.

**Files:**
- Modify: `intelligent_rag.py:66-104`

- [ ] **Step 1: Read the current `DCPR_ANSWER_RULES` block**

Run: Read `intelligent_rag.py` lines 66–104.
Expected: the constant begins with `DCPR_ANSWER_RULES = """MANDATORY ANSWER RULES:` and ends with `... cite them as [Web N] only."""`.

- [ ] **Step 2: Replace the entire constant**

Apply this exact replacement using the Edit tool. `old_string` is the full current block starting with `DCPR_ANSWER_RULES = """MANDATORY ANSWER RULES:` through the closing `"""`. `new_string` is:

```python
DCPR_ANSWER_RULES = """MANDATORY ANSWER RULES:
1. SCOPE — MUMBAI DCPR 2034 ONLY: You are an expert on DCPR 2034 for
   Mumbai. The retrieved excerpts are Mumbai DCPR 2034 only. If the
   question is about another city, another regulation (UDCPR, Pune),
   or a non-DCPR topic (property valuation, legal advice, market
   rates without a regulatory angle), reply in one line: "I cover
   only DCPR 2034 for Mumbai. Please ask within that scope." and
   stop. Do not attempt to answer from general knowledge.
2. ASKED-FACT BOUNDARY: Answer only the literal fact the user asked
   for. Include at most one short sentence of directly dependent
   context if the asked fact makes no sense without it. DO NOT
   volunteer adjacent regulations, tables, or limits that the user
   did not ask about.
   NEGATIVE EXAMPLE: If the user asks "TDR rates per ASR for
   generating and receiving plots", do NOT include FSI ceilings by
   road width (3 for 12m, 4 for 18m, 5 for 27m). Those are adjacent
   regulations. Answer only the TDR rate question. If the rate is
   not in the excerpts, say "Not specified in the retrieved DCPR
   excerpts." and stop.
3. DCPR-NATIVE UNITS ONLY: Quote every dimension, area, height, and
   width in the exact unit used in the DCPR excerpt. Never convert
   between metres and feet, or between sq.m and sq.ft. If the
   excerpt says "1.2 m × 1.0 m", the answer says "1.2 m × 1.0 m".
   NEGATIVE EXAMPLE: If the user asks "Minimum Toilet dimensions
   allowed" and the excerpt specifies the dimension in metres, do
   NOT answer "3' × 4' (approximately 12 sq. ft.)". Quote the
   metres value verbatim.
4. COMPARISON TABLE FOR MULTI-VARIANT REGULATIONS: When the
   retrieved excerpts describe ONE regulation with multiple variants
   (by space type, user type, building type, or similar) AND the
   user's question is broad enough to span those variants, render
   the answer as a markdown table with one row per variant. Do NOT
   use a table when only one variant applies or the user's question
   targets a single variant.
   POSITIVE EXAMPLE: "Parking requirement for educational institutes"
   spans office, assembly hall, visitor — render as a table.
   NEGATIVE EXAMPLE: "FSI for a 1000 sq.m plot on 12 m road" — one
   variant applies; use a prose sentence.
5. INLINE CITATION: Only emit a citation tag when you have BOTH a
   specific regulation/clause number AND a specific page number
   from the excerpts. The tag format is exactly:
   "— as per DCPR 2034, Regulation <X>, p.<N>"
   (or "Clause <X>" if that's how the excerpt labels it). The
   regulation number MUST come from the excerpt text; the page
   number MUST come from the [Doc N] header. NEVER emit the tag
   with empty slots.
6. "NOT SPECIFIED" SENTENCES GET NO CITATION: If you are saying
   the answer is not in the excerpts, do not append any citation
   tag to that sentence.
7. READ THE TABLES: Before saying "not specified", scan every
   excerpt for tables/schedules. DCPR tables frequently span
   multiple lines with pipe-separated cells; margins/FSI/parking
   are almost always in tables keyed to building height, plot
   size, or road width. Quote the exact row before stating the
   answer.
8. NO FABRICATION: Only state a number if it appears verbatim in
   the provided excerpts. Do not infer an FSI from a building
   height, or a margin from an FSI — these are independent fields
   in DCPR. If a value isn't in the excerpts, say "Not specified
   in the retrieved DCPR excerpts" in one line, no citation tag.
9. RAG IS THE SOURCE OF TRUTH: The DCPR excerpts are authoritative.
   Web search results are supplementary context only — use them
   for broader framing but NEVER let a web result override,
   contradict, or replace a value from the DCPR excerpts. If DCPR
   and web disagree, follow DCPR. If the DCPR excerpts do not
   contain the value, do not substitute a web number. Web results
   never earn a "— as per DCPR 2034..." citation; cite them as
   [Web N] only.
10. BREVITY: Target ≤6 short sentences plus one citation (tables
    excepted — table rows don't count toward the sentence limit).
    No section headers. No closing filler."""
```

- [ ] **Step 3: Sanity-check with grep**

Run: `grep -n "SCOPE — MUMBAI DCPR 2034 ONLY" intelligent_rag.py`
Expected: one match inside the constant.
Run: `grep -n "NEGATIVE EXAMPLE" intelligent_rag.py`
Expected: 3 matches (TDR→FSI, toilet units, FSI-single-variant inside rule 4).

- [ ] **Step 4: Commit**

```bash
git add intelligent_rag.py
git commit -m "rag: rewrite DCPR_ANSWER_RULES with Mumbai scope + asked-fact + DCPR-native-units + comparison-table rules"
```

---

## Task 2: Flip default location `"Pune"` → `"Mumbai"`

**Goal:** Change every hardcoded default location in query-analysis and fallback paths. This makes Mumbai the implicit target when the query doesn't mention a city.

**Files:**
- Modify: `intelligent_rag.py:1007`, `1124`, `1196-1198`, `1230`, `1241`, `1657`

- [ ] **Step 1: Flip line 1007 default**

Current: `location = "Pune"`
Edit using Edit tool with `old_string="location = \"Pune\"\n        if any(loc in q for loc in [\"mumbai\", \"navi mumbai\", \"thane\", \"nagpur\"]):"` and `new_string="location = \"Mumbai\"\n        if any(loc in q for loc in [\"mumbai\", \"navi mumbai\", \"thane\", \"nagpur\"]):"`.
Expected: one replacement at line 1007.

- [ ] **Step 2: Update line 1124 LLM instruction**

Current: `- "location": Specific area/locality mentioned (e.g., "Kothrud", "Hinjewadi", "Wakad"). Also extract city (Pune/Mumbai). Default to "Pune" if context suggests Maharashtra.`
Edit to: `- "location": Specific area/locality mentioned in Mumbai (e.g., "Andheri", "Bandra", "Goregaon"). Extract city only if explicitly stated. Default to "Mumbai" if not specified.`

Use the Edit tool with the full line as `old_string` to ensure uniqueness.

- [ ] **Step 3: Update lines 1196–1198 fallback**

Current:
```python
location=str(data.get("location", "Pune"))
if data.get("location")
else "Pune",
```
Edit to:
```python
location=str(data.get("location", "Mumbai"))
if data.get("location")
else "Mumbai",
```

- [ ] **Step 4: Update line 1230 exception fallback**

Current: `location="Pune",`
Context: inside the `except` block of `_analyze_query` around line 1219–1235.
Edit using `old_string="                compound_parts=[],\n                location=\"Pune\",\n                units={},"` and `new_string="                compound_parts=[],\n                location=\"Mumbai\",\n                units={},"`.

- [ ] **Step 5: Update line 1241 `_expand_queries` default**

Current: `location = context.location or "Pune"`
Edit to: `location = context.location or "Mumbai"`

- [ ] **Step 6: Update line 1657 `_synthesize_all` location detection**

Current:
```python
"location": "pune" if "pune" in question.lower() else None,
```
Edit to:
```python
"location": "mumbai" if "mumbai" in question.lower() else None,
```

- [ ] **Step 7: Sanity-check**

Run: `grep -n '"Pune"' intelligent_rag.py`
Expected: remaining hits should only be inside prompt f-strings (those are handled in Task 5). Count and record the remaining occurrences — should decrease from ~10 to ~5.

- [ ] **Step 8: Commit**

```bash
git add intelligent_rag.py
git commit -m "rag: flip default location from Pune to Mumbai in query-analysis defaults"
```

---

## Task 3: Remove UDCPR branch in `_expand_queries`

**Goal:** The corpus is DCPR 2034 only. The UDCPR branch only fired when `location == "pune"`, which is no longer a possible default. Remove the dead branch.

**Files:**
- Modify: `intelligent_rag.py:1242`

- [ ] **Step 1: Replace the conditional**

Edit using Edit tool:
- `old_string`: `        reg_type = "UDCPR" if str(location).lower() == "pune" else "DCPR 2034"`
- `new_string`: `        reg_type = "DCPR 2034"`

- [ ] **Step 2: Verify `reg_type` is still referenced downstream**

Run: `grep -n 'reg_type' intelligent_rag.py`
Expected: at least one usage below line 1242 (in query-expansion f-strings). If `reg_type` is no longer referenced anywhere after the assignment, delete the assignment line entirely.

- [ ] **Step 3: Commit**

```bash
git add intelligent_rag.py
git commit -m "rag: drop UDCPR branch — corpus is Mumbai DCPR 2034 only"
```

---

## Task 4: Clean Pune hardcodes from web-query f-strings

**Goal:** Four web-query templates hardcode `"Pune"` and Pune-specific localities. Replace them with generic Mumbai-friendly queries driven by `{context.location}`.

**Files:**
- Modify: `intelligent_rag.py:1486`, `1494`, `1781`, `1785`

- [ ] **Step 1: Update line 1486 `enhanced_web_query` (non-stream path)**

Current:
```python
enhanced_web_query = f"{context.location} {context.topic} property rates price per sqft 2025 2026 investment commercial IT parks yields"
```
No change required here — `{context.location}` already drives it, and "commercial IT parks" is generic. Leave as is. Verify by inspection.

- [ ] **Step 2: Update line 1494 `yield_query` (non-stream path)**

Current:
```python
yield_query = f"Pune {context.location} commercial property rental yields percentage Hinjewadi Kharadi Kalyani Nagar IT companies 2025"
```
Edit to:
```python
yield_query = f"{context.location} commercial property rental yields percentage IT companies 2025"
```

- [ ] **Step 3: Update line 1781 `enhanced_web_query` (stream path)**

Current:
```python
enhanced_web_query = f"{context.location} {context.topic} property rates price per sqft 2025 2026 investment"
```
No change required. Verify by inspection.

- [ ] **Step 4: Update line 1785 `yield_query` (stream path)**

Current:
```python
yield_query = f"Pune {context.location} commercial property rental yields percentage 2025"
```
Edit to:
```python
yield_query = f"{context.location} commercial property rental yields percentage 2025"
```

- [ ] **Step 5: Sanity-check**

Run: `grep -n "Pune" intelligent_rag.py`
Expected: no `"Pune "` prefix remaining in web-query f-strings. Remaining hits are inside prompt templates (handled in Task 5) and inside the comment at line 1657 detection (already handled in Task 2).

Run: `grep -n "Hinjewadi\|Kothrud\|Kalyani Nagar\|Kharadi" intelligent_rag.py`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add intelligent_rag.py
git commit -m "rag: drop Pune-locality hardcodes from web-search queries"
```

---

## Task 5: Rewrite prompt templates (system + user) to Mumbai DCPR framing

**Goal:** Strip Pune/UDCPR framing from the three prompt templates and two system messages. Every prompt now frames the model as a Mumbai DCPR 2034 expert.

**Files:**
- Modify: `intelligent_rag.py:1982-2000`, `2002-2020`, `2023-2042`, `2045-2061`, `2070`, `2125-2141`, `2143-2161`, `2178-2201`, `2208`

There are five prompt locations. Each one needs the same two changes:
- Any "Pune" / "Pune and Mumbai" / "Pune, Maharashtra" → "Mumbai"
- Any "DCPR/UDCPR" → "DCPR 2034"
- `or "Pune"` fallback → `or "Mumbai"`

### Subtask 5a: `_generate_dynamic_answer` technical prompt (lines 1982–2000)

- [ ] **Step 1: Apply edits**

Edit the prompt string to change:
- `"You are a senior Urban Planning Consultant specializing in Pune and Mumbai DCPR/UDCPR."` → `"You are a senior Urban Planning Consultant on DCPR 2034 for Mumbai."`
- `Location: {context.location or "Pune"}` → `Location: {context.location or "Mumbai"}`

Use two `Edit` calls or a single `Edit` targeting a unique multiline span.

### Subtask 5b: `_generate_dynamic_answer` comparison-market prompt (lines 2002–2020)

- [ ] **Step 1: Apply edit**

- `"You are a real estate investment advisor for Pune, Maharashtra. Provide a ranked list based on web search data."` → `"You are a real estate investment advisor for Mumbai. Provide a ranked list based on web search data."`

### Subtask 5c: `_generate_dynamic_answer` feasibility prompt (lines 2023–2042)

- [ ] **Step 1: Apply edits**

- `"You are a real estate investment advisor for Pune and Mumbai, Maharashtra. Provide a focused feasibility analysis."` → `"You are a real estate investment advisor for Mumbai. Provide a focused feasibility analysis."`
- `Location: {context.location or "Pune"}` → `Location: {context.location or "Mumbai"}`

### Subtask 5d: `_generate_dynamic_answer` standard regulatory prompt (lines 2045–2061)

- [ ] **Step 1: Apply edits**

- `"You are a Pune urban planning expert answering a DCPR question."` → `"You are a Mumbai urban planning expert answering a DCPR 2034 question."`
- `Location={context.location or "Pune"}` → `Location={context.location or "Mumbai"}`
- `"DCPR/UDCPR Regulations:"` → `"DCPR 2034 Regulations:"`

### Subtask 5e: `_generate_dynamic_answer` system message (line 2070)

- [ ] **Step 1: Apply edit**

Current:
```
"You are a Pune urban planning expert. Answer ONLY what is asked, in under 6 short sentences, with exact numbers from the DCPR excerpts. ..."
```
Edit to:
```
"You are a Mumbai DCPR 2034 expert. Answer ONLY what is asked, in under 6 short sentences, with exact numbers from the DCPR excerpts. ..."
```
(Preserve the rest of the system-message text verbatim.)

### Subtask 5f: `_stream_dynamic_answer` technical prompt (lines 2125–2141)

- [ ] **Step 1: Apply edit**

Current first line: `"You are a high-precision Urban Planning Expert answering a DCPR question."`
No Pune reference in this prompt — confirm by reading. If no change needed, skip this subtask.

### Subtask 5g: `_stream_dynamic_answer` feasibility prompt (lines 2143–2161)

- [ ] **Step 1: Apply edits**

- `"You are a real estate investment advisor for Pune and Mumbai, Maharashtra. Provide a focused feasibility analysis."` → `"You are a real estate investment advisor for Mumbai. Provide a focused feasibility analysis."`
- `Location: {context.location or "Pune"}` → `Location: {context.location or "Mumbai"}`

### Subtask 5h: `_stream_dynamic_answer` standard prompt (lines 2178–2201)

- [ ] **Step 1: Apply edits**

- `"You are an expert urban planning consultant for Pune, Maharashtra. Answer using the DCPR/UDCPR excerpts below."` → `"You are an expert urban planning consultant for Mumbai. Answer using the DCPR 2034 excerpts below."`
- `loc_str = query_params.get("location", "Pune (default)")` → `loc_str = query_params.get("location", "Mumbai (default)")`
- `"DCPR/UDCPR Regulation Excerpts:"` → `"DCPR 2034 Regulation Excerpts:"`

### Subtask 5i: `_stream_dynamic_answer` system message (line 2208)

- [ ] **Step 1: Apply edit**

Current:
```
"You are a helpful urban planning expert for Pune/Mumbai DCPR. Keep answers short ..."
```
Edit to:
```
"You are a helpful urban planning expert on DCPR 2034 for Mumbai. Keep answers short ..."
```
(Preserve the rest of the system-message text verbatim.)

### Subtask 5j: Sanity-check

- [ ] **Step 1: Verify no Pune references remain**

Run: `grep -n "Pune" intelligent_rag.py`
Expected: zero matches.

Run: `grep -n "UDCPR" intelligent_rag.py`
Expected: zero matches.

If any remain, identify them and patch inline.

### Subtask 5k: Commit

- [ ] **Step 1: Commit**

```bash
git add intelligent_rag.py
git commit -m "rag: rewrite prompt templates to Mumbai DCPR 2034 framing"
```

---

## Task 6: Update frontend UI copy

**Goal:** Remove Pune/UDCPR references from user-facing UI strings.

**Files:**
- Modify: `Dhara-frontend/src/app/chat/page.tsx:218`, `240`, `394`, `560`

- [ ] **Step 1: Update error fallback at lines 218 and 240 (identical strings)**

Edit using Edit tool with `replace_all=true`:
- `old_string`: `I apologize, but I couldn't process your query at the moment. Please try again or rephrase your question about DCPR/UDCPR regulations.`
- `new_string`: `I apologize, but I couldn't process your query at the moment. Please try again or rephrase your question about DCPR 2034 regulations.`

Expected: 2 replacements (lines 218 and 240).

- [ ] **Step 2: Update placeholder at line 394**

Edit:
- `old_string`: `Ask about DCPR 2034, building regulations, FSI lookups, or property feasibility in Pune.`
- `new_string`: `Ask about DCPR 2034, building regulations, FSI lookups, or property feasibility in Mumbai.`

- [ ] **Step 3: Update footer at line 560**

Edit:
- `old_string`: `Pune UDCPR 2024 &bull; DCPR 2034 &bull; AI Powered`
- `new_string`: `DCPR 2034 &bull; AI Powered`

- [ ] **Step 4: Sanity-check**

Run: `grep -n "Pune\|UDCPR" Dhara-frontend/src/app/chat/page.tsx`
Expected: zero matches.

- [ ] **Step 5: Commit**

```bash
git add Dhara-frontend/src/app/chat/page.tsx
git commit -m "ui: remove Pune/UDCPR references — Mumbai DCPR 2034 only"
```

---

## Task 7: Validation — replay session-33 questions

**Goal:** Confirm the four failure modes are fixed and no regressions were introduced on the three working answers.

**Files:** None modified in this task.

- [ ] **Step 1: Start the backend**

Run: `bash start.sh` (in a separate terminal).
Expected: the `api.py` server starts on its configured port and Milvus is reachable.

- [ ] **Step 2: Replay question 1 — Minimum Toilet dimensions allowed**

Run (CLI):
```bash
python3 cli.py query "Minimum Toilet dimensions allowed"
```
Expected PASS criteria:
- Dimensions are in metres (e.g., `1.2 m × 1.0 m`), NOT in feet or sq.ft.
- No parenthetical unit conversion.
- If the excerpt does not contain the value, reply is exactly "Not specified in the retrieved DCPR excerpts."

- [ ] **Step 3: Replay question 2 — TDR rates per ASR**

Run:
```bash
python3 cli.py query "TDR generated and receiving plots rates of land as per ASR"
```
Expected PASS criteria:
- Answer does NOT mention FSI ceilings by road width (3 for 12m, 4 for 18m, 5 for 27m).
- Answer focuses only on the TDR rate question.
- If the ASR rate is not in the corpus, answer is "Not specified in the retrieved DCPR excerpts." and stops.

- [ ] **Step 4: Replay question 3 — Parking for educational institutes**

Run:
```bash
python3 cli.py query "Parking requirement for educational institutes in Mumbai"
```
Expected PASS criteria:
- Answer is rendered as a markdown table with one row per variant (office / assembly / visitor etc.).
- Not a prose summary.

- [ ] **Step 5: Replay question 4 — Staircases in high-rise (regression)**

Run:
```bash
python3 cli.py query "Number of staircases required in high rise building and its criteria"
```
Expected PASS criteria:
- Answer still correct and cites DCPR 2034, Clause 48 (or similar).
- No regression vs. the session-33 answer.

- [ ] **Step 6: Replay question 5 — FSI on 12m road (regression)**

Run:
```bash
python3 cli.py query "FSI for 1000 square meter plot on 12 meter road"
```
Expected PASS criteria:
- Answer still correct, cites DCPR 2034 Regulation 33(4) or similar.
- Mumbai framing (not Pune) in any inferred location language.

- [ ] **Step 7: Replay question 6 — Amenity plot (regression)**

Run:
```bash
python3 cli.py query "Requirement of Amenity Plot for industrial to residential"
```
Expected PASS criteria:
- Answer still correct and cites DCPR 2034, Regulation 43(A).
- No regression.

- [ ] **Step 8: Record results**

Create a short validation log in the PR description (or inline in the commit) listing:
- Question
- PASS / FAIL
- One-line note (what was right, what was wrong)

No code commit for this task.

- [ ] **Step 9: If any question FAILs, patch**

If a question fails:
1. Identify which rule in `DCPR_ANSWER_RULES` was ignored.
2. Strengthen the rule wording (add a sharper negative example, move the rule higher in the list).
3. Re-run the failing question only.
4. Commit the fix as `rag: tighten <rule> — fix <question-name> regression`.
5. Re-run the full six-question battery once more.

---

## Self-review notes

- Spec coverage: R1 → Task 1 rule 1 + Task 5 + Task 6. R2 → Task 1 rule 2. R3 → Task 1 rule 3. R4 → Task 1 rule 4. Pune/UDCPR cleanup → Tasks 2, 3, 4, 5, 6. Validation → Task 7.
- No placeholders: every edit has exact `old_string` → `new_string` or a well-defined edit target.
- Type consistency: no types introduced; string edits only.
- Commit cadence: 6 commits (one per task, Task 7 no commit). Clean revert path.
