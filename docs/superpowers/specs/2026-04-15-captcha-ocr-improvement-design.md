# Captcha OCR Improvement — PR Card Scraper

**Date:** 2026-04-15
**Service:** `services/pr_card_scraper`
**Goal:** Improve captcha solving accuracy, reduce LLM API costs, and handle form reset errors intelligently.

---

## Problem Statement

The PR card scraper automates form submission on the Mahabhumi Bhulekh website. The site presents a 6-character alphanumeric CAPTCHA (mixed case + digits) that must be solved to submit. Current issues:

1. **Low first-try accuracy** — similar-looking characters (O/0/o, q/g, l/1/I, S/5, Z/2) cause frequent misreads, burning through retry attempts.
2. **LLM cost/latency** — Gemini Flash is called on every attempt as Tier 1, even for captchas that offline OCR could handle.
3. **Wasted retries on form data errors** — when form data is wrong but captcha was correct, the current code re-fills the form AND re-solves captcha unnecessarily. Error types are not distinguished.

## Captcha Characteristics

Based on analysis of 30+ saved captcha images from `services/outputs/`:

- 6 characters: uppercase letters, lowercase letters, digits
- Case-sensitive
- Clean font on light/white background
- Minor dot noise, no heavy distortion or warping
- No colored backgrounds or overlapping lines

## Design

### 1. Improved LLM Prompt

**File:** `services/pr_card_scraper/services/llm_captcha_solver.py`

Replace the generic prompt:

```
"What text is shown in this image? Reply with ONLY the exact characters, nothing else. Case-sensitive."
```

With a captcha-specific prompt:

```
"This is a 6-character CAPTCHA image containing a mix of uppercase letters, lowercase letters, and digits. Characters are case-sensitive. Pay close attention to these commonly confused pairs: O (uppercase letter) vs 0 (digit, narrower), o (lowercase) vs 0 (digit); Q (has tail) vs O (no tail); q (descender curves left) vs g (descender curves right); l (lowercase L) vs 1 (digit) vs I (uppercase i); S vs 5; Z vs 2; B vs 8. Reply with ONLY the exact 6 characters, nothing else."
```

For OpenAI, request `n: 2` completions to get a second opinion cheaply. For Gemini (which doesn't support `n`), make a second call only when the first result contains any character from the confusable set (`0OoQqgIl1Ss5Zz2Bb8`). Both results feed into candidate ranking.

### 2. Smarter Error Classification + Retry Strategy

**Files:** `services/pr_card_scraper/services/browser/__init__.py`, `services/pr_card_scraper/services/browser/mahabhumi.py`

#### Error types from dialog messages

After form submission, classify the error dialog:

| Error Type | Dialog keywords | Form fields | Captcha |
|-----------|----------------|-------------|---------|
| `captcha_error` | "captcha", "wrong code", "incorrect code" | Stay filled | Refreshes |
| `data_error` | "select", "enter", "निवडा", "भरा", "not found", "सापडले नाही" | May be cleared | Refreshes |
| `unknown_error` | Anything else | Unknown | Refreshes |

#### Changes to `submit_form`

Return a structured error instead of a generic `RuntimeError`:

```python
class SubmitError(Exception):
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type  # "captcha_error" | "data_error" | "unknown_error"
```

#### Changes to `_solve_captcha_loop`

- On `captcha_error`: Do NOT re-fill form fields (they're intact). Just get new captcha and solve.
- On `data_error`: Re-fill form fields, then get new captcha and solve.
- On `unknown_error`: Treat as data error (re-fill + new captcha).
- Keep 5 max attempts total.
- Log error type distinctly for debugging and tracking failure rates.

### 3. OCR-First Strategy with Confidence Gating

**File:** `services/pr_card_scraper/services/captcha_solver.py`

Flip the tier order: **ddddocr first, LLM second**.

#### Confidence gating logic

```
ddddocr_raw = solve with raw image
ddddocr_preprocessed = solve with best preprocessed variant

if ddddocr_raw == ddddocr_preprocessed and length == 6:
    HIGH confidence → return result, skip LLM
elif ddddocr_raw or ddddocr_preprocessed produced a 6-char result:
    MEDIUM confidence → call LLM as tiebreaker, use consensus
else:
    LOW confidence → call LLM as primary
```

This reduces LLM calls to only the cases where offline OCR is uncertain.

### 4. Simplified Preprocessing Pipeline

**File:** `services/pr_card_scraper/services/captcha_solver.py`

The current pipeline applies heavy transforms (morphological line removal, multiple binary thresholds) designed for noisy captchas. The Mahabhumi captchas are clean, so these transforms can damage character shapes.

New pipeline (ordered by effectiveness for these captchas):

1. **Grayscale + median filter** (removes dot noise without blurring edges)
2. **3x upscale** (LANCZOS) + contrast boost (more pixel detail for similar chars)
3. **Otsu thresholding** (auto-adaptive binary, better than fixed thresholds)
4. **Sharpen** (enhance character edges)

Keep the current heavy pipeline as a fallback variant but try the simplified one first.

### 5. Expanded Confusion Pairs + Case-Aware Variants

**File:** `services/pr_card_scraper/services/captcha_solver.py`

#### New confusion pairs

Add to the existing list:

```python
("q", "g"),   # descender direction
("o", "0"),   # lowercase o vs digit
("o", "O"),   # case
("n", "h"),   # similar body
("rn", "m"),  # ligature confusion
("d", "cl"),  # shape confusion
```

#### Case-aware variant ranking

When generating confusion variants, rank by visual similarity in the captcha font:

- `0` (digit) misread → try `O` (upper) before `o` (lower), because uppercase O is visually closer to 0 in this font
- `l` (lower L) misread → try `1` (digit) before `I` (upper i)
- `q` misread → try `g` first (both have descenders)

### 6. Consensus Scoring

**File:** `services/pr_card_scraper/services/captcha_solver.py`

When both ddddocr and LLM return results, compare character-by-character:

- **Characters agree** → high confidence, use as-is
- **Characters disagree** → prefer LLM result at that position, but generate the ddddocr character as a variant
- Build a merged "best guess" + ranked variant list from disagreements

## Files Changed

| File | Change |
|------|--------|
| `llm_captcha_solver.py` | New captcha-specific prompt, dual completion for OpenAI, optional second Gemini call |
| `captcha_solver.py` | ddddocr-first with confidence gating, simplified preprocessing, expanded confusion pairs, case-aware ranking, consensus scoring |
| `browser/__init__.py` | Error classification in retry loop, skip re-fill on captcha-only errors, distinct error type logging |
| `mahabhumi.py` | `submit_form` raises `SubmitError` with `error_type` field instead of generic `RuntimeError` |

## What Does NOT Change

- 5 retry attempts max
- Playwright browser automation + stealth
- Captcha image capture logic (`get_captcha_image`, `refresh_captcha`)
- Form filling logic (`fill_form`)
- pytesseract as last-resort fallback
- Debug image saving to `outputs/`
- Network interception for PR card image extraction

## Testing Strategy

- Run against saved captcha images in `outputs/` to verify preprocessing + OCR improvements offline
- Compare old vs new accuracy on the same image set
- End-to-end test with the live Mahabhumi site to verify error classification and retry behavior
- Monitor LLM call count before/after to verify cost reduction
