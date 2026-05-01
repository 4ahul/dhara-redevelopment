"""
LLM Vision CAPTCHA Solver
Gemini 2.5 Flash (primary) → GPT-4o (fallback).
Returns a single high-confidence answer per call.
"""

import base64
import io
import logging
import os

import httpx
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

_PROMPT = (
    "This CAPTCHA image has exactly 6 case-sensitive alphanumeric characters "
    "(a-z, A-Z, 0-9). Watch for confusable characters: "
    "O vs 0 (letter vs digit), o vs 0, l vs 1 vs I, q vs g, n vs h, S vs 5, Z vs 2, B vs 8. "
    "Reply with ONLY the 6 characters, nothing else."
)

_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def _clean(text: str) -> str:
    cleaned = "".join(c for c in text.strip() if c in _ALLOWED)
    return cleaned if 4 <= len(cleaned) <= 8 else ""


def _enhance_for_llm(image_bytes: bytes) -> str:
    """Enlarge 3x + denoise + contrast + sharpen → base64."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    img = img.resize((w * 3, h * 3), Image.LANCZOS)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class LLMCaptchaSolver:
    """Solves CAPTCHAs via LLM vision APIs."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = openai_base_url or os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

    async def solve(self, image_bytes: bytes) -> str | None:
        """
        Try Gemini Flash first, then OpenAI. Returns cleaned text or None.
        """
        # Enhance image for better LLM vision (2x upscale + contrast)
        b64 = _enhance_for_llm(image_bytes)

        # 1. Gemini 2.0 Flash (cheapest, fastest)
        if self.gemini_api_key:
            result = await self._gemini_solve(b64)
            if result:
                return result

        # 2. OpenAI GPT-4o fallback
        if self.openai_api_key:
            result = await self._openai_solve(b64)
            if result:
                return result

        return None

    async def _gemini_solve(self, b64_image: str) -> str | None:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
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
            "generationConfig": {
                "maxOutputTokens": 256,
                "temperature": 0,
                "thinkingConfig": {"thinkingBudget": 0},
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=5.0)
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

    async def _openai_solve(self, b64_image: str) -> str | None:
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
                    "content": "You are an OCR assistant that reads text from images. Always respond with only the text content.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "auto",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 10,
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=5.0)
                resp.raise_for_status()
                data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            cleaned = _clean(text)
            if cleaned:
                logger.info("OpenAI CAPTCHA: '%s' -> '%s'", text.strip(), cleaned)
                return cleaned
            logger.warning("OpenAI returned unusable text: '%s'", text.strip())
        except Exception as e:
            logger.warning("OpenAI CAPTCHA failed: %s", e)
        return None
