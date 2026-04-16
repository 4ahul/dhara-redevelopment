# Captcha OCR Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve captcha solving accuracy for the Mahabhumi PR card scraper by enhancing the LLM prompt, flipping to OCR-first with confidence gating, adding error classification, and expanding confusion-pair handling.

**Architecture:** Four files change: `mahabhumi.py` gets a `SubmitError` with error type classification, `browser/__init__.py` uses that to skip unnecessary form re-fills, `captcha_solver.py` flips to ddddocr-first with confidence gating and better preprocessing, and `llm_captcha_solver.py` gets a captcha-specific prompt.

**Tech Stack:** Python, Pillow, OpenCV, ddddocr, pytesseract, httpx (Gemini/OpenAI APIs), Playwright

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `services/pr_card_scraper/services/browser/mahabhumi.py` | Modify (lines 697-742) | `SubmitError` exception class, error type classification in `submit_form` |
| `services/pr_card_scraper/services/browser/__init__.py` | Modify (lines 205-281) | `_solve_captcha_loop` uses error types to skip re-fill on captcha errors |
| `services/pr_card_scraper/services/captcha_solver.py` | Modify (full file) | OCR-first strategy, confidence gating, simplified preprocessing, expanded confusion pairs, consensus scoring |
| `services/pr_card_scraper/services/llm_captcha_solver.py` | Modify (full file) | New captcha-specific prompt, dual completion support |
| `services/pr_card_scraper/tests/__init__.py` | Create | Test package init |
| `services/pr_card_scraper/tests/test_captcha_solver.py` | Create | Unit tests for captcha solver |
| `services/pr_card_scraper/tests/test_llm_captcha_solver.py` | Create | Unit tests for LLM captcha solver |
| `services/pr_card_scraper/tests/test_submit_error.py` | Create | Unit tests for error classification |

---

### Task 1: Add SubmitError with Error Type Classification

**Files:**
- Modify: `services/pr_card_scraper/services/browser/mahabhumi.py:697-742`
- Create: `services/pr_card_scraper/tests/__init__.py`
- Create: `services/pr_card_scraper/tests/test_submit_error.py`

- [ ] **Step 1: Create test directory and write failing test**

Create `services/pr_card_scraper/tests/__init__.py` (empty file).

Create `services/pr_card_scraper/tests/test_submit_error.py`:

```python
"""Tests for SubmitError and error type classification."""

from services.browser.mahabhumi import SubmitError, classify_submit_error


def test_captcha_error_detected():
    msg = "Captcha code is wrong"
    err = classify_submit_error(msg)
    assert err.error_type == "captcha_error"


def test_captcha_error_marathi():
    msg = "कृपया captcha पुन्हा लिहा"
    err = classify_submit_error(msg)
    assert err.error_type == "captcha_error"


def test_data_error_select():
    msg = "कृपया जिल्हा निवडा"
    err = classify_submit_error(msg)
    assert err.error_type == "data_error"


def test_data_error_english():
    msg = "Please select a valid district"
    err = classify_submit_error(msg)
    assert err.error_type == "data_error"


def test_data_error_not_found():
    msg = "Record not found सापडले नाही"
    err = classify_submit_error(msg)
    assert err.error_type == "data_error"


def test_unknown_error_fallback():
    msg = "Something unexpected happened"
    err = classify_submit_error(msg)
    assert err.error_type == "unknown_error"


def test_submit_error_has_message():
    err = SubmitError("test message", "captcha_error")
    assert str(err) == "test message"
    assert err.error_type == "captcha_error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_submit_error.py -v`
Expected: FAIL — `SubmitError` and `classify_submit_error` don't exist yet.

- [ ] **Step 3: Implement SubmitError and classify_submit_error**

Add to the top of `services/pr_card_scraper/services/browser/mahabhumi.py` (after imports):

```python
class SubmitError(Exception):
    """Raised when form submission fails. error_type is one of:
    'captcha_error', 'data_error', 'unknown_error'."""
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type


_CAPTCHA_KEYWORDS = ["captcha", "wrong code", "incorrect code", "कॅप्चा"]
_DATA_KEYWORDS = [
    "निवडा", "select", "enter", "correct", "invalid",
    "कृपया", "भरा", "not found", "सापडले नाही", "error6", "try again"
]


def classify_submit_error(dialog_message: str) -> SubmitError:
    """Classify a dialog message into captcha_error, data_error, or unknown_error."""
    msg = dialog_message.lower()
    if any(kw in msg for kw in _CAPTCHA_KEYWORDS):
        return SubmitError(dialog_message, "captcha_error")
    if any(kw in msg for kw in _DATA_KEYWORDS):
        return SubmitError(dialog_message, "data_error")
    return SubmitError(dialog_message, "unknown_error")
```

Then update `submit_form` to use it. Replace the existing error handling block (lines 716-740):

```python
            if self._last_dialog_message:
                raise classify_submit_error(self._last_dialog_message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_submit_error.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/pr_card_scraper/services/browser/mahabhumi.py services/pr_card_scraper/tests/
git commit -m "feat: add SubmitError with captcha/data error classification"
```

---

### Task 2: Update Captcha Retry Loop with Error-Aware Logic

**Files:**
- Modify: `services/pr_card_scraper/services/browser/__init__.py:205-281`

- [ ] **Step 1: Implement error-aware retry loop**

Replace the `_solve_captcha_loop` method (lines 205-281) in `services/pr_card_scraper/services/browser/__init__.py`:

```python
    async def _solve_captcha_loop(
        self, form_handler: MahabhumiFormHandler, extractor: ImageExtractor,
        on_captcha, form_kwargs: dict = None
    ) -> Optional[dict]:
        """
        Auto-solve CAPTCHA with error-aware retry strategy.

        Error classification:
          - captcha_error: form fields stay filled, just solve new captcha
          - data_error: re-fill form fields, then solve new captcha
          - unknown_error: treat as data_error

        Returns a result dict on failure/captcha_required, or None on success.
        """
        from .mahabhumi import SubmitError

        max_attempts = 5
        last_captcha_img = None
        last_error_type = None

        for attempt in range(max_attempts):
            # Re-fill form only if last error was a data/unknown error
            if attempt > 0 and last_error_type in ("data_error", "unknown_error") and form_kwargs:
                logger.info("Re-filling form after data error")
                try:
                    await form_handler.fill_form(**form_kwargs)
                except Exception as e:
                    logger.warning("Form re-fill failed: %s — trying CAPTCHA anyway", e)
            elif attempt > 0 and last_error_type == "captcha_error":
                logger.info("Captcha-only error — form fields intact, skipping re-fill")
            elif attempt > 0 and last_error_type is None:
                # No submission happened (no candidates) — just refresh captcha
                await form_handler.refresh_captcha()

            # Wait for CAPTCHA image to settle
            await asyncio.sleep(1)

            captcha_img = await form_handler.get_captcha_image()
            last_captcha_img = captcha_img
            img_size = len(captcha_img) if captcha_img else 0
            logger.info("CAPTCHA attempt %d/%d: %d bytes", attempt + 1, max_attempts, img_size)

            if not captcha_img or img_size < 200:
                logger.warning("CAPTCHA image too small or empty — will retry")
                last_error_type = None
                continue

            candidates = await self.captcha_solver.solve(captcha_img)

            if not candidates:
                logger.warning("No candidates for attempt %d/%d", attempt + 1, max_attempts)
                last_error_type = None
                continue

            captcha_text = candidates[0]
            logger.info("Trying CAPTCHA: %r (attempt %d/%d)", captcha_text, attempt + 1, max_attempts)
            try:
                await form_handler.submit_form(captcha_text)
                logger.info("CAPTCHA accepted: %r", captcha_text)
                return None  # success
            except SubmitError as e:
                last_error_type = e.error_type
                logger.info("CAPTCHA %r rejected (type=%s): %s", captcha_text, e.error_type, e)
            except Exception as e:
                last_error_type = "unknown_error"
                logger.info("CAPTCHA %r rejected (unknown): %s", captcha_text, e)

        # Exhausted all retries — try manual callback if available
        if on_captcha and last_captcha_img:
            manual = await on_captcha(last_captcha_img)
            if manual:
                try:
                    await form_handler.submit_form(manual)
                    return None
                except Exception:
                    pass

        return {
            "status": "captcha_required",
            "captcha_image": last_captcha_img,
            "error": "CAPTCHA failed after all retries",
        }
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd services/pr_card_scraper && python -c "from services.browser import MahabhumiScraper; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/pr_card_scraper/services/browser/__init__.py
git commit -m "feat: error-aware captcha retry — skip re-fill on captcha-only errors"
```

---

### Task 3: Improve LLM Captcha Prompt and Add Dual Completion

**Files:**
- Modify: `services/pr_card_scraper/services/llm_captcha_solver.py` (full file)
- Create: `services/pr_card_scraper/tests/test_llm_captcha_solver.py`

- [ ] **Step 1: Write failing tests**

Create `services/pr_card_scraper/tests/test_llm_captcha_solver.py`:

```python
"""Tests for LLM captcha solver utilities."""

from services.llm_captcha_solver import _clean, _enhance_for_llm, _PROMPT
import base64


def test_clean_valid_6_chars():
    assert _clean("AbC12d") == "AbC12d"


def test_clean_strips_whitespace_and_junk():
    assert _clean("  Ab!C@1#2d\n") == "AbC12d"


def test_clean_rejects_too_short():
    assert _clean("Ab1") == ""


def test_clean_rejects_too_long():
    assert _clean("AbCd12345") == ""


def test_prompt_mentions_6_characters():
    assert "6-character" in _PROMPT


def test_prompt_mentions_case_sensitive():
    assert "case-sensitive" in _PROMPT.lower() or "Case-sensitive" in _PROMPT


def test_prompt_mentions_confusion_pairs():
    # Must mention at least O vs 0 and q vs g
    assert "O" in _PROMPT and "0" in _PROMPT
    assert "q" in _PROMPT and "g" in _PROMPT


def test_enhance_for_llm_returns_valid_base64():
    # Create a minimal 10x10 white PNG
    from PIL import Image
    import io
    img = Image.new("RGB", (10, 10), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    b64 = _enhance_for_llm(raw)
    decoded = base64.b64decode(b64)
    # Should be a valid PNG (starts with PNG magic bytes)
    assert decoded[:4] == b'\x89PNG'

    # Should be upscaled — output image is 3x larger
    result_img = Image.open(io.BytesIO(decoded))
    assert result_img.size == (30, 30)  # 10*3 = 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_llm_captcha_solver.py -v`
Expected: Some tests FAIL (prompt tests fail because old prompt doesn't mention 6-character, confusion pairs; enhance test fails because current upscale is 2x not 3x).

- [ ] **Step 3: Update the LLM captcha solver**

Replace the full content of `services/pr_card_scraper/services/llm_captcha_solver.py`:

```python
"""
LLM Vision CAPTCHA Solver
Gemini 2.0 Flash (primary) → GPT-4o (fallback).
Returns a single high-confidence answer per call.
"""

import base64
import io
import logging
import os
from typing import Optional, List

import httpx
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

_PROMPT = (
    "This is a 6-character CAPTCHA image containing a mix of uppercase letters, "
    "lowercase letters, and digits. Characters are case-sensitive. "
    "Pay close attention to these commonly confused pairs: "
    "O (uppercase letter, round) vs 0 (digit, narrower); "
    "o (lowercase, small round) vs 0 (digit); "
    "Q (has tail extending down-right) vs O (no tail); "
    "q (descender curves left) vs g (descender curves right); "
    "l (lowercase L, straight vertical) vs 1 (digit, may have serif) vs I (uppercase i); "
    "n (short vertical + hump) vs h (tall vertical + hump); "
    "S (uppercase) vs 5 (digit, flat top); "
    "Z (uppercase) vs 2 (digit, curved bottom); "
    "B (uppercase) vs 8 (digit). "
    "Reply with ONLY the exact 6 characters, nothing else."
)

_CONFUSABLE_CHARS = set("0OoQqgIl1Ss5Zz2Bb8nhrm")

_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def _clean(text: str) -> str:
    cleaned = "".join(c for c in text.strip() if c in _ALLOWED)
    return cleaned if 4 <= len(cleaned) <= 8 else ""


def _enhance_for_llm(image_bytes: bytes) -> str:
    """Enlarge 3x + denoise + boost contrast -> base64. Helps LLMs read small noisy text."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    img = img.resize((w * 3, h * 3), Image.LANCZOS)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _has_confusable(text: str) -> bool:
    """Check if result contains characters from the confusable set."""
    return any(c in _CONFUSABLE_CHARS for c in text)


class LLMCaptchaSolver:
    """Solves CAPTCHAs via LLM vision APIs."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = (
            openai_base_url
            or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )

    async def solve(self, image_bytes: bytes) -> List[str]:
        """
        Try Gemini Flash first, then OpenAI. Returns list of cleaned candidates.
        If the first result contains confusable characters, makes a second call
        for a second opinion.
        """
        b64 = _enhance_for_llm(image_bytes)
        candidates: List[str] = []

        # 1. Gemini 2.0 Flash
        if self.gemini_api_key:
            result = await self._gemini_solve(b64)
            if result:
                candidates.append(result)
                # Second call if confusable characters detected
                if _has_confusable(result):
                    second = await self._gemini_solve(b64)
                    if second and second != result:
                        candidates.append(second)

        # 2. OpenAI GPT-4o fallback (only if Gemini returned nothing)
        if not candidates and self.openai_api_key:
            results = await self._openai_solve(b64, n=2)
            candidates.extend(results)

        return candidates

    async def _gemini_solve(self, b64_image: str) -> Optional[str]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 10, "temperature": 0},
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=8.0)
                resp.raise_for_status()
                data = resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            cleaned = _clean(text)
            if cleaned:
                logger.info("Gemini CAPTCHA: '%s' -> '%s'", text.strip(), cleaned)
                return cleaned
            logger.warning("Gemini returned unusable text: '%s'", text.strip())
        except Exception as e:
            logger.warning("Gemini CAPTCHA failed: %s", e)
        return None

    async def _openai_solve(self, b64_image: str, n: int = 1) -> List[str]:
        """Call OpenAI with n completions and return all valid cleaned results."""
        url = f"{self.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a CAPTCHA reader. Read the exact characters from the image. Case-sensitive. Reply with ONLY the characters.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 10,
            "temperature": 0,
            "n": n,
        }
        results: List[str] = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=payload, headers=headers, timeout=8.0
                )
                resp.raise_for_status()
                data = resp.json()
            for choice in data.get("choices", []):
                text = choice.get("message", {}).get("content", "")
                cleaned = _clean(text)
                if cleaned:
                    logger.info("OpenAI CAPTCHA: '%s' -> '%s'", text.strip(), cleaned)
                    if cleaned not in results:
                        results.append(cleaned)
                else:
                    logger.warning("OpenAI returned unusable text: '%s'", text.strip())
        except Exception as e:
            logger.warning("OpenAI CAPTCHA failed: %s", e)
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_llm_captcha_solver.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/pr_card_scraper/services/llm_captcha_solver.py services/pr_card_scraper/tests/test_llm_captcha_solver.py
git commit -m "feat: captcha-specific LLM prompt with confusion-pair guidance and dual completion"
```

---

### Task 4: Rewrite Captcha Solver — OCR-First with Confidence Gating

**Files:**
- Modify: `services/pr_card_scraper/services/captcha_solver.py` (full file)
- Create: `services/pr_card_scraper/tests/test_captcha_solver.py`

- [ ] **Step 1: Write failing tests**

Create `services/pr_card_scraper/tests/test_captcha_solver.py`:

```python
"""Tests for CaptchaSolver — preprocessing, cleaning, confidence, variants."""

import io
import pytest
from PIL import Image
from services.captcha_solver import CaptchaSolver, _ALLOWED, _CONFUSION_PAIRS


def _make_white_image(w=120, h=40) -> bytes:
    """Create a minimal white PNG image as bytes."""
    img = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestClean:
    def test_valid_6_chars(self):
        solver = CaptchaSolver()
        assert solver._clean("AbC12d") == "AbC12d"

    def test_strips_junk(self):
        solver = CaptchaSolver()
        assert solver._clean("Ab!C@1#2d") == "AbC12d"

    def test_rejects_short(self):
        solver = CaptchaSolver()
        assert solver._clean("Ab1") == ""

    def test_rejects_long(self):
        solver = CaptchaSolver()
        assert solver._clean("AbCd12345") == ""

    def test_preserves_case(self):
        solver = CaptchaSolver()
        assert solver._clean("aBcDeF") == "aBcDeF"


class TestConfusionPairs:
    def test_has_qg_pair(self):
        """q/g confusion pair must exist."""
        pairs_flat = [(a, b) for a, b in _CONFUSION_PAIRS]
        assert ("q", "g") in pairs_flat or ("g", "q") in pairs_flat

    def test_has_o0_pair(self):
        """o/0 confusion pair must exist."""
        pairs_flat = [(a, b) for a, b in _CONFUSION_PAIRS]
        assert ("o", "0") in pairs_flat or ("0", "o") in pairs_flat

    def test_has_oO_pair(self):
        """o/O confusion pair must exist."""
        pairs_flat = [(a, b) for a, b in _CONFUSION_PAIRS]
        assert ("o", "O") in pairs_flat or ("O", "o") in pairs_flat

    def test_has_nh_pair(self):
        """n/h confusion pair must exist."""
        pairs_flat = [(a, b) for a, b in _CONFUSION_PAIRS]
        assert ("n", "h") in pairs_flat or ("h", "n") in pairs_flat


class TestConfusionVariants:
    def test_generates_variants(self):
        solver = CaptchaSolver()
        variants = solver._confusion_variants("AbC0qS")
        # Should include at least O-for-0, g-for-q, 5-for-S
        assert any("O" in v for v in variants)
        assert any("g" in v for v in variants)
        assert any("5" in v for v in variants)

    def test_does_not_include_original(self):
        solver = CaptchaSolver()
        original = "AbCdEf"
        variants = solver._confusion_variants(original)
        assert original not in variants

    def test_case_variants_included(self):
        solver = CaptchaSolver()
        variants = solver._confusion_variants("AbCdEf")
        assert "ABCDEF" in variants or "abcdef" in variants


class TestConfidenceGating:
    def test_high_confidence_when_raw_and_preprocessed_agree(self):
        solver = CaptchaSolver()
        confidence = solver._assess_confidence("AbC12d", "AbC12d")
        assert confidence == "high"

    def test_medium_confidence_when_results_differ(self):
        solver = CaptchaSolver()
        confidence = solver._assess_confidence("AbC12d", "AbC12D")
        assert confidence == "medium"

    def test_low_confidence_when_one_is_empty(self):
        solver = CaptchaSolver()
        confidence = solver._assess_confidence("AbC12d", "")
        assert confidence == "low"

    def test_low_confidence_when_both_empty(self):
        solver = CaptchaSolver()
        confidence = solver._assess_confidence("", "")
        assert confidence == "low"


class TestConsensus:
    def test_consensus_prefers_agreed_chars(self):
        solver = CaptchaSolver()
        merged = solver._consensus_merge("AbC0qS", "AbCOgS")
        # Positions 0,1,2,5 agree (A,b,C,S). Positions 3,4 disagree.
        # First arg (ocr) chars at disagreement: 0, q
        # Second arg (llm) chars at disagreement: O, g
        # LLM preferred at disagreement positions
        assert merged[0] == "AbCOgS"  # LLM preferred for disagreements
        assert len(merged) >= 2  # At least one variant


class TestPreprocessingPipeline:
    def test_pipeline_yields_multiple_variants(self):
        solver = CaptchaSolver()
        img = Image.new("RGB", (120, 40), "white")
        variants = list(solver._preprocessing_pipeline(img))
        assert len(variants) >= 3
        for preprocessed, label in variants:
            assert isinstance(preprocessed, Image.Image)
            assert isinstance(label, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_captcha_solver.py -v`
Expected: Multiple FAILs — `_assess_confidence`, `_consensus_merge` don't exist, `q/g` pair missing.

- [ ] **Step 3: Rewrite captcha_solver.py**

Replace the full content of `services/pr_card_scraper/services/captcha_solver.py`:

```python
"""
CAPTCHA solver — OCR-first with confidence gating:
  1. ddddocr (primary OCR, offline) — try raw + preprocessed
  2. Confidence gate — if OCR agrees with itself, skip LLM
  3. LLM Vision (Gemini Flash → GPT-4o) — tiebreaker for uncertain OCR
  4. pytesseract — last resort
Returns a list of candidate strings (most likely first).
"""

import io
import logging
from typing import List, Tuple, Optional

from PIL import Image, ImageEnhance, ImageFilter

from .llm_captcha_solver import LLMCaptchaSolver

logger = logging.getLogger(__name__)

_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")

_CONFUSION_PAIRS = [
    ("0", "O"),
    ("0", "o"),
    ("o", "O"),
    ("1", "I"),
    ("1", "l"),
    ("I", "l"),
    ("S", "5"),
    ("Z", "2"),
    ("B", "8"),
    ("G", "6"),
    ("D", "0"),
    ("Q", "0"),
    ("q", "g"),
    ("n", "h"),
]


class CaptchaSolver:
    """OCR-first CAPTCHA solver with LLM tiebreaker."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self._reader = None
        self._tesseract_available = None
        self._llm_solver = LLMCaptchaSolver()

    def _reader_instance(self):
        if self._reader is None:
            logger.info("Loading ddddocr model...")
            import ddddocr
            self._reader = ddddocr.DdddOcr(show_ad=False)
            logger.info("ddddocr model loaded")
        return self._reader

    def _check_tesseract(self) -> bool:
        if self._tesseract_available is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
            except Exception:
                self._tesseract_available = False
        return self._tesseract_available

    async def solve(self, image_bytes: bytes) -> List[str]:
        """
        Solve CAPTCHA — OCR first, LLM as tiebreaker.
        Returns a deduplicated list of candidate strings (most likely first).
        """
        # ── Step 1: ddddocr on raw + preprocessed ──────────────────────
        ocr_raw = self._ocr_single(image_bytes, "raw")
        ocr_preprocessed = self._ocr_best_preprocessed(image_bytes)

        # ── Step 2: Confidence gating ──────────────────────────────────
        confidence = self._assess_confidence(ocr_raw, ocr_preprocessed)
        logger.info(
            "OCR results — raw: %r, preprocessed: %r, confidence: %s",
            ocr_raw, ocr_preprocessed, confidence,
        )

        candidates: List[str] = []

        if confidence == "high":
            # OCR agrees with itself — skip LLM, save money
            logger.info("High confidence OCR — skipping LLM")
            candidates.append(ocr_raw)
        elif confidence == "medium":
            # OCR disagrees — call LLM as tiebreaker
            llm_candidates = await self._llm_solve(image_bytes)
            if llm_candidates:
                # Consensus merge: use LLM at disagreement positions
                merged = self._consensus_merge(ocr_raw, llm_candidates[0])
                candidates.extend(merged)
                # Also add raw LLM and OCR results
                for c in llm_candidates:
                    if c not in candidates:
                        candidates.append(c)
            # Add OCR results as fallback
            for c in [ocr_raw, ocr_preprocessed]:
                if c and c not in candidates:
                    candidates.append(c)
        else:
            # Low confidence — LLM is primary
            llm_candidates = await self._llm_solve(image_bytes)
            candidates.extend(llm_candidates)
            # pytesseract as last resort
            tess_results = self._tesseract_solve(image_bytes)
            for c in tess_results:
                if c not in candidates:
                    candidates.append(c)

        # ── Step 3: Add confusion variants for top candidates ──────────
        return self._build_variant_list(candidates)

    async def _llm_solve(self, image_bytes: bytes) -> List[str]:
        """Call LLM solver and return candidates."""
        try:
            results = await self._llm_solver.solve(image_bytes)
            if results:
                logger.info("LLM CAPTCHA results: %s", results)
                return results
        except Exception as e:
            logger.warning("LLM CAPTCHA solver error: %s", e)
        return []

    def _ocr_single(self, image_bytes: bytes, label: str = "raw") -> str:
        """Run ddddocr on raw image bytes. Returns cleaned text or empty string."""
        try:
            reader = self._reader_instance()
            text = reader.classification(image_bytes)
            cleaned = self._clean(text)
            if cleaned:
                logger.debug("ddddocr %s: '%s' -> '%s'", label, text, cleaned)
                return cleaned
        except Exception as e:
            logger.warning("ddddocr %s failed: %s", label, e)
        return ""

    def _ocr_best_preprocessed(self, image_bytes: bytes) -> str:
        """Run ddddocr on the best preprocessed variant. Returns first valid result."""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            reader = self._reader_instance()

            for preprocessed, label in self._preprocessing_pipeline(img):
                with io.BytesIO() as bio:
                    preprocessed.save(bio, format="PNG")
                    res_bytes = bio.getvalue()
                text = reader.classification(res_bytes)
                cleaned = self._clean(text)
                if cleaned:
                    logger.debug("ddddocr %s: '%s' -> '%s'", label, text, cleaned)
                    return cleaned
        except Exception as e:
            logger.warning("ddddocr preprocessing failed: %s", e)
        return ""

    def _tesseract_solve(self, image_bytes: bytes) -> List[str]:
        """pytesseract fallback. Returns list of cleaned candidates."""
        if not self._check_tesseract():
            return []
        results = []
        try:
            import pytesseract
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            config = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            for preprocessed, label in self._preprocessing_pipeline(img):
                try:
                    text = pytesseract.image_to_string(preprocessed, config=config)
                    cleaned = self._clean(text)
                    if cleaned and cleaned not in results:
                        results.append(cleaned)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("pytesseract failed: %s", e)
        return results

    def _preprocessing_pipeline(self, img: Image.Image):
        """Simplified pipeline tuned for Mahabhumi captchas (clean text, light bg, dot noise)."""
        gray = img.convert("L")

        # 1. Denoise + contrast (best for these clean captchas)
        denoised = gray.filter(ImageFilter.MedianFilter(size=3))
        enhanced = ImageEnhance.Contrast(denoised).enhance(3.0)
        yield enhanced, "denoise_contrast"

        # 2. 3x upscale + contrast + sharpen (more detail for similar chars)
        w, h = gray.size
        big = gray.resize((w * 3, h * 3), Image.LANCZOS)
        big = big.filter(ImageFilter.MedianFilter(size=3))
        big = ImageEnhance.Contrast(big).enhance(2.5)
        big = ImageEnhance.Sharpness(big).enhance(1.5)
        yield big, "upscaled_3x"

        # 3. Otsu-style thresholding (auto-adaptive)
        try:
            import cv2
            import numpy as np
            arr = np.array(gray)
            _, otsu = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            yield Image.fromarray(otsu), "otsu"
        except ImportError:
            # Fallback: fixed threshold
            yield gray.point(lambda p: 255 if p > 128 else 0), "binary_128"

        # 4. High contrast grayscale (simple, works well)
        sharp = ImageEnhance.Sharpness(gray).enhance(2.0)
        sharp_contrast = ImageEnhance.Contrast(sharp).enhance(2.5)
        yield sharp_contrast, "sharp_contrast"

    def _assess_confidence(self, ocr_raw: str, ocr_preprocessed: str) -> str:
        """Assess confidence based on OCR agreement.
        Returns: 'high', 'medium', or 'low'.
        """
        if ocr_raw and ocr_preprocessed and ocr_raw == ocr_preprocessed:
            return "high"
        if ocr_raw or ocr_preprocessed:
            return "medium"
        return "low"

    def _consensus_merge(self, ocr_text: str, llm_text: str) -> List[str]:
        """Merge OCR and LLM results character-by-character.
        Where they agree, use the agreed character.
        Where they disagree, prefer LLM but add OCR variant.
        Returns: [merged_best, ...variants].
        """
        if not ocr_text or not llm_text:
            return [t for t in [llm_text, ocr_text] if t]

        # Align by length — use the shorter length
        min_len = min(len(ocr_text), len(llm_text))
        merged = []
        ocr_variant = []

        for i in range(min_len):
            if ocr_text[i] == llm_text[i]:
                merged.append(llm_text[i])
                ocr_variant.append(llm_text[i])
            else:
                merged.append(llm_text[i])  # prefer LLM
                ocr_variant.append(ocr_text[i])  # OCR as variant

        # Append remaining chars from the longer string
        if len(llm_text) > min_len:
            merged.extend(llm_text[min_len:])
            ocr_variant.extend(llm_text[min_len:])
        elif len(ocr_text) > min_len:
            merged.extend(ocr_text[min_len:])
            ocr_variant.extend(ocr_text[min_len:])

        merged_str = "".join(merged)
        ocr_variant_str = "".join(ocr_variant)

        result = [merged_str]
        if ocr_variant_str != merged_str:
            result.append(ocr_variant_str)
        return result

    def _clean(self, text: str) -> str:
        cleaned = "".join(c for c in text.strip() if c in _ALLOWED)
        return cleaned if 4 <= len(cleaned) <= 8 else ""

    def _build_variant_list(self, candidates: List[str]) -> List[str]:
        """Build final candidate list with confusion variants for top results."""
        if not candidates:
            return []

        seen = set()
        result: List[str] = []

        for text in candidates[:3]:  # Top 3 candidates get variants
            if text and text not in seen:
                seen.add(text)
                result.append(text)
            for variant in self._confusion_variants(text):
                if variant not in seen:
                    seen.add(variant)
                    result.append(variant)

        logger.info("Final candidates (%d): %s", len(result), result[:10])
        return result

    def _confusion_variants(self, text: str) -> List[str]:
        if not text:
            return []
        variants = set()

        def _expand(current: str, pair_idx: int):
            if pair_idx >= len(_CONFUSION_PAIRS):
                if 4 <= len(current) <= 8:
                    variants.add(current)
                return
            a, b = _CONFUSION_PAIRS[pair_idx]
            _expand(current, pair_idx + 1)
            if a in current:
                _expand(current.replace(a, b), pair_idx + 1)
            if b in current:
                _expand(current.replace(b, a), pair_idx + 1)

        _expand(text, 0)
        variants.discard(text)

        variants.add(text.upper())
        variants.add(text.lower())
        variants.discard(text)

        return [v for v in variants if 4 <= len(v) <= 8]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_captcha_solver.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/pr_card_scraper/services/captcha_solver.py services/pr_card_scraper/tests/test_captcha_solver.py
git commit -m "feat: OCR-first captcha solver with confidence gating and consensus scoring"
```

---

### Task 5: End-to-End Validation with Saved Captcha Images

**Files:**
- Create: `services/pr_card_scraper/tests/test_captcha_e2e.py`

- [ ] **Step 1: Write a test that runs the solver against saved captcha images**

Create `services/pr_card_scraper/tests/test_captcha_e2e.py`:

```python
"""
Offline end-to-end test: run CaptchaSolver against saved captcha images.
Not a pass/fail unit test — prints results for manual inspection.
Run with: python -m pytest tests/test_captcha_e2e.py -v -s
"""

import asyncio
import os
import glob

import pytest

from services.captcha_solver import CaptchaSolver


OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "outputs")


def _get_captcha_images():
    pattern = os.path.join(OUTPUTS_DIR, "captcha_*.png")
    files = sorted(glob.glob(pattern))
    return files


@pytest.fixture(scope="module")
def solver():
    return CaptchaSolver()


@pytest.mark.skipif(
    not _get_captcha_images(),
    reason="No saved captcha images found in outputs/",
)
class TestCaptchaE2E:
    def test_solver_produces_candidates_for_each_image(self, solver):
        """Each saved captcha image should produce at least 1 candidate."""
        files = _get_captcha_images()
        results = []

        for f in files[:10]:  # Test first 10 images
            with open(f, "rb") as fh:
                image_bytes = fh.read()
            candidates = asyncio.get_event_loop().run_until_complete(
                solver.solve(image_bytes)
            )
            basename = os.path.basename(f)
            results.append((basename, candidates))
            print(f"\n{basename}: {candidates[:5]}")

        # At least 80% of images should produce candidates
        with_candidates = sum(1 for _, c in results if c)
        total = len(results)
        rate = with_candidates / total if total else 0
        print(f"\nCandidate rate: {with_candidates}/{total} ({rate:.0%})")
        assert rate >= 0.8, f"Only {rate:.0%} of images produced candidates"

    def test_candidates_are_valid_length(self, solver):
        """All candidates should be 4-8 chars, alphanumeric only."""
        files = _get_captcha_images()
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")

        for f in files[:5]:
            with open(f, "rb") as fh:
                image_bytes = fh.read()
            candidates = asyncio.get_event_loop().run_until_complete(
                solver.solve(image_bytes)
            )
            for c in candidates:
                assert 4 <= len(c) <= 8, f"Invalid length for '{c}' from {os.path.basename(f)}"
                assert all(ch in allowed for ch in c), f"Invalid chars in '{c}' from {os.path.basename(f)}"
```

- [ ] **Step 2: Run the e2e test**

Run: `cd services/pr_card_scraper && python -m pytest tests/test_captcha_e2e.py -v -s`
Expected: PASS with printed candidates for each image. Inspect output to verify OCR quality.

- [ ] **Step 3: Commit**

```bash
git add services/pr_card_scraper/tests/test_captcha_e2e.py
git commit -m "test: add offline e2e captcha solver validation against saved images"
```

---

### Task 6: Final Integration Verification

- [ ] **Step 1: Verify all imports resolve**

Run: `cd services/pr_card_scraper && python -c "from services.browser import MahabhumiScraper; from services.captcha_solver import CaptchaSolver; from services.llm_captcha_solver import LLMCaptchaSolver; from services.browser.mahabhumi import SubmitError, classify_submit_error; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: Run all tests**

Run: `cd services/pr_card_scraper && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit any remaining changes**

```bash
git add -A services/pr_card_scraper/
git commit -m "chore: final integration verification for captcha OCR improvements"
```
