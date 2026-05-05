"""
LLM Vision PR Card Data Extractor
Gemini 2.5 Flash (primary) -> GPT-4o (fallback).
Extracts structured fields from Property Card images.
"""

import base64
import io
import json
import logging
import os
import re

import httpx
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

_PROMPT = """You are a document data extractor for Indian government Property Cards (PR Cards) from the Maharashtra Mahabhumi portal.

Extract ALL fields from this Property Card image into the following JSON structure.
If a field is not visible or unreadable, use null.

{
  "property_uid": "string or null",
  "village_patti": "string or null",
  "taluka": "string or null",
  "district": "string or null",
  "cts_no": "string or null",
  "sheet_number": "string or null",
  "plot_number": "string or null",
  "area_sqm": number or null,
  "tenure": "string or null",
  "assessment": "string or null",
  "survey_year": "string or null",
  "holders": [{"name": "string", "share": "string or null"}],
  "encumbrances": "string or null",
  "other_remarks": "string or null",
  "transactions": [{"date": "string", "transaction_type": "string", "vol_no": "string", "new_holder": "string"}]
}

Reply with ONLY valid JSON. No markdown, no explanation, no code fences."""


def _prepare_image(image_bytes: bytes) -> str:
    """Enlarge 2x + boost contrast -> base64 PNG. Helps LLMs read document text."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _parse_json_response(text: str) -> dict | None:
    """Parse LLM response as JSON, with fallback for markdown-wrapped responses."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _compute_confidence(data: dict) -> str:
    """Compute extraction confidence based on key fields."""
    has_cts = data.get("cts_no") is not None
    has_area = data.get("area_sqm") is not None
    has_holders = bool(data.get("holders"))

    if has_cts and has_area:
        return "high"
    if has_cts or has_area or has_holders:
        return "medium"
    return "low"


def _validate_area(data: dict) -> dict:
    """Validate and clean area_sqm field."""
    area = data.get("area_sqm")
    if area is not None:
        try:
            area = float(area)
            if not (0.1 <= area <= 100000):
                logger.warning("area_sqm out of range (%.2f), setting to null", area)
                data["area_sqm"] = None
            else:
                data["area_sqm"] = area
        except (ValueError, TypeError):
            data["area_sqm"] = None
    return data


class LLMDataExtractor:
    """Extract structured data from PR card images using LLM Vision."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = openai_base_url or os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

    async def extract(self, image_bytes: bytes) -> dict:
        """
        Extract structured data from PR card image.
        Gemini Flash (primary) -> GPT-4o (fallback).
        Returns parsed dict with metadata, or empty dict on total failure.
        """
        if not self.gemini_api_key and not self.openai_api_key:
            logger.warning("No LLM API keys configured for PR card extraction")
            return {}

        b64 = _prepare_image(image_bytes)

        # Try Gemini first
        if self.gemini_api_key:
            result = await self._gemini_extract(b64)
            if result:
                result = _validate_area(result)
                result["extraction_confidence"] = _compute_confidence(result)
                result["extraction_source"] = self.gemini_model
                return result

        # Fallback to GPT-4o
        if self.openai_api_key:
            result = await self._openai_extract(b64)
            if result:
                result = _validate_area(result)
                result["extraction_confidence"] = _compute_confidence(result)
                result["extraction_source"] = "gpt-4o"
                return result

        logger.warning("All LLM extraction attempts failed")
        return {}

    async def _gemini_extract(self, b64_image: str) -> dict | None:
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
                "maxOutputTokens": 2048,
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
                resp = await client.post(url, json=payload, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            parsed = _parse_json_response(text)
            if parsed:
                logger.info("Gemini PR card extraction succeeded")
                return parsed
            logger.warning("Gemini returned unparseable response: %s", text[:200])
        except Exception as e:
            logger.warning("Gemini PR card extraction failed: %s", e)
        return None

    async def _openai_extract(self, b64_image: str) -> dict | None:
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
                    "content": "You are a document data extractor for Indian government Property Cards. Always respond with only valid JSON.",
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
            "max_tokens": 1024,
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_response(text)
            if parsed:
                logger.info("OpenAI PR card extraction succeeded")
                return parsed
            logger.warning("OpenAI returned unparseable response: %s", text[:200])
        except Exception as e:
            logger.warning("OpenAI PR card extraction failed: %s", e)
        return None


# Backward-compatible alias — old code imports DataExtractor
DataExtractor = LLMDataExtractor
