# DCPR Answer-Quality & Mumbai-Scope Cleanup — Design

**Date:** 2026-04-18
**Owner:** Rahul
**Scope:** Prompt + UI-copy changes to fix four production feedback items from chat session 33.

---

## 1. Problem

Session 33 replay surfaced four recurring failure modes in the RAG assistant's answers:

1. **Scope drift** — a question about TDR rates per ASR returned FSI ceilings by road width. The user asked about transferable-development-rights rates; the bot volunteered an adjacent regulation.
2. **Wrong units** — "Minimum Toilet dimensions allowed" returned *3' × 4' (~12 sq.ft)*. The source DCPR document specifies dimensions in metres; the bot converted to imperial without being asked.
3. **No comparison when broad** — "Parking requirement for educational institutes" returned a prose summary of several variants (office, assembly, visitor). A table would have been clearer.
4. **Pune/UDCPR framing** — prompts and UI still reference Pune and UDCPR 2024, but the embedded corpus is DCPR 2034 for Mumbai only. The Pune framing misleads users and pushes the LLM to default to the wrong city.

Secondary constraint: RAG must remain the source of truth; web search is reference only (already enforced by rule #7 in `DCPR_ANSWER_RULES`).

## 2. Goals

- Eliminate the four failure modes above without retrieval or pipeline changes.
- Single-commit, easily reversible.
- No new dependencies, no latency regression.

## 3. Non-Goals

- Retrieval re-ranking, re-indexing, embedding model change.
- Post-generation LLM guard / second-pass scope-check (explicitly deferred; revisit only if prompt-only enforcement proves insufficient after one week of production use).
- Automated regression tests for prompts (validation is manual replay of the 6 session-33 questions).

## 4. Decisions & Rules

| # | Rule | Rationale |
|---|------|-----------|
| R1 | **Mumbai DCPR only** — system identity is "Mumbai DCPR 2034 expert". Out-of-scope questions get a one-line decline. | Corpus is Mumbai DCPR. Pune/UDCPR framing misleads. |
| R2 | **Asked-fact boundary** — answer only the literal fact asked plus the minimum dependent context needed for it to make sense. Do not volunteer adjacent regulations. | TDR→FSI drift. "Be helpful" is being mis-applied. |
| R3 | **DCPR-native units** — quote every value in the exact unit used by the DCPR excerpt. No m↔ft, no sq.m↔sq.ft conversion. | Toilet example returned sq.ft when source was in metres. |
| R4 | **Comparison table for multi-variant regulations** — when retrieved excerpts describe one regulation with multiple variants (space type, user type, building type) and the question is broad enough to span them, render as a markdown table. | Parking-for-educational-institutes was a prose blob. |

R2 is the most load-bearing rule. Enforcement relies on:
- Explicit negative example in the prompt (TDR→FSI drift shown as "do not do this").
- Rule phrasing that specifies the boundary ("answer the asked fact; do not volunteer adjacent regulations").

## 5. Architecture

No architectural change. Edits localized to two files:

| File | Nature of change |
|------|------------------|
| `intelligent_rag.py` | Rewrite `DCPR_ANSWER_RULES` constant; update 3 per-intent prompt templates; flip default `location` from `"Pune"` to `"Mumbai"`; remove UDCPR branch and Pune-specific web-query hardcodes. |
| `Dhara-frontend/src/app/chat/page.tsx` | 3 UI string updates: footer, placeholder copy, error-fallback copy. |

## 6. Detailed Changes

### 6.1 `intelligent_rag.py`

#### `DCPR_ANSWER_RULES` (current line 66)

Rewrite to encode R1–R4 in priority order. Preserve existing mandates (citation format, no fabrication, "Not specified" handling, RAG > web). Add two concrete negative examples inside the rules block:

- TDR→FSI drift example: "If asked about TDR rates, do not list FSI ceilings by road width. Answer only the TDR rate question."
- Unit conversion example: "If asked for minimum toilet dimensions and the excerpt says '1.2 m × 1.0 m', answer in metres verbatim. Do not convert to sq.ft."

#### Prompt templates

Three prompts currently carry Pune framing and need rewrite to Mumbai:

- `_generate_dynamic_answer` (line ~2045) — "Pune urban planning expert" → "Mumbai DCPR 2034 expert".
- `_stream_dynamic_answer` technical branch (line ~2125) — same framing update.
- `_stream_dynamic_answer` standard branch (line ~2178) — same framing update.
- `_synthesize_all` (line ~1667) — detects `"pune"` in query; keep detection but change default from Pune to Mumbai.

System messages (lines 2070, 2208) — "Pune urban planning expert" / "Pune/Mumbai DCPR" → "Mumbai DCPR 2034 expert".

#### Default location

Flip `"Pune"` → `"Mumbai"` at:
- Line 1007 (initial default)
- Line 1124 (LLM prompt for query analysis — "Default to 'Pune'" → "Default to 'Mumbai'")
- Lines 1196, 1198, 1230 (fallbacks on LLM parse failure)
- Line 1241 (answer-side default in `_expand_queries`)
- Line 1657 (`_synthesize_all` location detection)
- Lines 2026, 2048, 2146, 2173 (prompt variable defaults)

#### UDCPR branch

Line 1242:
```python
reg_type = "UDCPR" if str(location).lower() == "pune" else "DCPR 2034"
```
Replace with:
```python
reg_type = "DCPR 2034"
```

#### Web-query Pune hardcodes

Lines 1486, 1494, 1781, 1785 contain f-strings that hardcode `"Pune"` and Pune-specific localities (Hinjewadi, Kothrud, Kalyani Nagar, Kharadi). Remove every hardcoded locality list, drop the leading `"Pune "` prefix, and rely on `{context.location}` alone (which now defaults to Mumbai). The resulting query shape is `f"{context.location} {context.topic} ..."`.

### 6.2 `Dhara-frontend/src/app/chat/page.tsx`

| Line | Current | New |
|------|---------|-----|
| 218 | `...DCPR/UDCPR regulations.` | `...DCPR 2034 regulations.` |
| 240 | `...DCPR/UDCPR regulations.` | `...DCPR 2034 regulations.` |
| 394 | `Ask about DCPR 2034, building regulations, FSI lookups, or property feasibility in Pune.` | `Ask about DCPR 2034, building regulations, FSI lookups, or property feasibility in Mumbai.` |
| 560 | `Pune UDCPR 2024 • DCPR 2034 • AI Powered` | `DCPR 2034 • AI Powered` |

## 7. Validation

Manual replay of the six questions from session 33:

| Q | Expected behavior |
|---|-------------------|
| Minimum Toilet dimensions allowed | Answer in metres (source unit). No sq.ft. |
| Number of staircases in high-rise | Unchanged (regression check). |
| FSI for 1000 sq.m plot on 12 m road | Unchanged (regression check). |
| Parking requirement for educational institutes | Rendered as markdown table with variants. |
| Amenity plot for industrial→residential | Unchanged (regression check). |
| TDR rates per ASR | Must NOT mention FSI ceilings by road width. Answers only the TDR rate question; says "Not specified in the retrieved DCPR excerpts" if the rate is not in corpus. |

Run each through the UI or `cli.py query` against the updated code. Pass = behavior matches the expected column.

## 8. Risk & Rollback

- Single commit touching two files. Rollback = `git revert <sha>`. No DB migrations, no cache invalidation, no index rebuild.
- Primary risk: prompt rules are best-effort — the LLM may still occasionally drift on R2 for edge cases. Mitigation: explicit negative example in the prompt. Escalation: if drift persists after one week of production, add a second-pass scope-check LLM call (Option 2 in brainstorming, deferred here).
- Secondary risk: removing the UDCPR branch and Pune hardcodes could affect any Pune-specific query flow. Mitigation: the corpus is Mumbai-only, so Pune flows were already returning wrong answers; this is a correctness improvement, not a regression.

## 9. Out of Scope

- Retrieval changes.
- Post-generation validator / second-pass LLM call.
- Automated prompt tests.
- Removing the `"pune"` keyword from `_synthesize_all` query-parameter detection (harmless if retained; corpus won't match).

## 10. Open Questions

None at time of writing. All four feedback items have a user-approved rule; prompt and UI edits are enumerated above.
