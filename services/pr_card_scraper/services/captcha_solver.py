"""
CAPTCHA solver — 3-tier strategy:
  1. LLM Vision (Gemini Flash → GPT-4o-mini) — fast, accurate
  2. ddddocr (primary OCR) — offline fallback
  3. pytesseract — last resort
Returns a list of candidate strings (most likely first).
"""

import io
import logging
from typing import List

from PIL import Image, ImageEnhance

from .llm_captcha_solver import LLMCaptchaSolver

logger = logging.getLogger(__name__)

_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")

_CONFUSION_PAIRS = [
    ("0", "O"),
    ("0", "o"),
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
    """3-tier CAPTCHA solver: LLM → ddddocr → pytesseract."""

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
        Solve CAPTCHA — tries LLM first (high accuracy), falls back to OCR.
        Returns a deduplicated list of candidate strings (most likely first).
        """
        candidates: List[str] = []

        # ── Tier 1: LLM Vision (Gemini Flash → GPT-4o-mini) ─────────────
        try:
            llm_result = await self._llm_solver.solve(image_bytes)
            if llm_result:
                logger.info("LLM CAPTCHA result: '%s'", llm_result)
                candidates.append(llm_result)
        except Exception as e:
            logger.warning("LLM CAPTCHA solver error: %s", e)

        # ── Tier 2 & 3: OCR fallback ────────────────────────────────────
        ocr_candidates = self._ocr_solve(image_bytes)
        for c in ocr_candidates:
            if c not in candidates:
                candidates.append(c)

        return candidates

    def _ocr_solve(self, image_bytes: bytes) -> List[str]:
        """Original OCR-based solver (ddddocr + pytesseract)."""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            w, h = img.size
            if w > 300 or h > 150:
                img = self._crop_captcha_region(img)

            candidates: List[tuple] = []

            # ddddocr
            try:
                reader = self._reader_instance()

                raw_text = reader.classification(image_bytes)
                cleaned = self._clean(raw_text)
                if cleaned:
                    candidates.append((1.0, cleaned, "raw"))

                for preprocessed, label in self._preprocessing_pipeline(img):
                    with io.BytesIO() as bio:
                        preprocessed.save(bio, format="PNG")
                        res_bytes = bio.getvalue()
                    text = reader.classification(res_bytes)
                    cleaned = self._clean(text)
                    if cleaned:
                        candidates.append((0.9, cleaned, label))

            except Exception as e:
                logger.warning("ddddocr failed: %s", e)

            # pytesseract fallback
            if not candidates and self._check_tesseract():
                import pytesseract

                config = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                for preprocessed, label in self._preprocessing_pipeline(img):
                    try:
                        text = pytesseract.image_to_string(preprocessed, config=config)
                        cleaned = self._clean(text)
                        if cleaned:
                            candidates.append((0.5, cleaned, f"tess_{label}"))
                    except Exception:
                        pass

            if not candidates:
                return []

            return self._build_variant_list(candidates)

        except Exception as e:
            logger.error("OCR solver failed: %s", e, exc_info=True)
            return []

    def _preprocessing_pipeline(self, img):
        gray = img.convert("L")
        yield gray, "gray"

        enhanced = ImageEnhance.Contrast(gray).enhance(3.0)
        yield enhanced, "high_contrast"

        sharpened = ImageEnhance.Sharpness(gray).enhance(2.0)
        sharp_contrast = ImageEnhance.Contrast(sharpened).enhance(2.5)
        yield sharp_contrast, "sharp_contrast"

        try:
            import cv2
            import numpy as np

            arr = np.array(gray)

            adaptive = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            yield Image.fromarray(adaptive), "adaptive_thresh"

            _, binary = cv2.threshold(arr, 127, 255, cv2.THRESH_BINARY_INV)
            h_kernel = np.ones((1, 15), np.uint8)
            h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=1)
            cleaned = binary - h_lines
            v_kernel = np.ones((15, 1), np.uint8)
            v_lines = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, v_kernel, iterations=1)
            cleaned = cleaned - v_lines
            kernel_dilate = np.ones((2, 2), np.uint8)
            dilated = cv2.dilate(cleaned, kernel_dilate, iterations=1)
            result_cv2 = cv2.bitwise_not(dilated)
            yield Image.fromarray(result_cv2), "cv2_cleaned"

        except ImportError:
            pass

        for t in [100, 128, 160]:
            thresh = gray.point(lambda p, th=t: 255 if p > th else 0)
            yield thresh, f"binary_{t}"

        w, h = gray.size
        big = gray.resize((w * 2, h * 2), Image.LANCZOS)
        big_enhanced = ImageEnhance.Contrast(big).enhance(2.0)
        yield big_enhanced, "upscaled_2x"

    def _crop_captcha_region(self, img):
        w, h = img.size
        left = int(w * 0.38)
        top = int(h * 0.44)
        right = int(w * 0.58)
        bottom = int(h * 0.52)
        return img.crop((left, top, right, bottom))

    def _clean(self, text: str) -> str:
        cleaned = "".join(c for c in text.strip() if c in _ALLOWED)
        return cleaned if 4 <= len(cleaned) <= 8 else ""

    def _build_variant_list(self, candidates: list) -> List[str]:
        if not candidates:
            return []

        candidates.sort(key=lambda x: x[0], reverse=True)

        seen: dict = {}
        for conf, text, _label in candidates:
            if text not in seen:
                seen[text] = conf

        result: List[str] = []

        for text in list(seen.keys())[:2]:
            if text not in result:
                result.append(text)
            for variant in self._confusion_variants(text):
                if variant not in result:
                    result.append(variant)

        logger.info("OCR candidates (%d): %s", len(result), result[:10])
        return result

    def _confusion_variants(self, text: str) -> List[str]:
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
