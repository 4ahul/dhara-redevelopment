"""
AI Client utilities - Shared helpers for AI imports and clients.
"""

import os
import sys
import sysconfig
from typing import Any


def get_genai_client(api_key: str) -> tuple[Any, Any]:
    """
    Import google.genai, working around the google namespace package conflict.
    Handles both venv and system site-packages paths.
    """
    try:
        from google import genai as _genai
        from google.genai import types as _types

        return _genai.Client(api_key=api_key), _types
    except ImportError:
        pass

    import importlib

    user_sp = sysconfig.get_path("purelib")

    extra_paths = []

    if sys.platform == "win32":
        base = sysconfig.get_path("base")
        if base:
            extra_paths.append(f"{base}\\Lib\\site-packages")

        local_app_data = getattr(sys, "local_app_data", None)
        if local_app_data:
            extra_paths.append(f"{local_app_data}\\Programs\\Python\\Python314\\Lib\\site-packages")

    common_paths = [
        "/usr/local/lib/python3.12/site-packages",
        "/usr/lib/python3.12/site-packages",
        "/opt/python3.12/lib/python3.12/site-packages",
    ]

    candidate_paths = [user_sp] + extra_paths + common_paths

    for path in candidate_paths:
        if path and path not in sys.path:
            sys.path.insert(0, path)

    try:
        _genai_mod = importlib.import_module("google.genai")
        _types_mod = importlib.import_module("google.genai.types")
        return _genai_mod.Client(api_key=api_key), _types_mod
    except Exception as e:
        raise ImportError(f"google-genai not available: {e}") from e


async def resolve_address_with_ai(address: str, api_key: str | None = None) -> dict:
    """
    Use Google Gemini AI to extract ward, village, taluka, district from address.
    """
    import re

    if not api_key:
        return {}

    try:
        client, gtypes = get_genai_client(api_key)

        prompt = f"""Extract location details from this Mumbai address. Return ONLY a JSON object with these fields:
- ward (BMC ward code e.g. "K/W", "G/S", "H/E", "E")
- village (neighbourhood e.g. "Vile Parle", "Dharavi", "Kurla")
- taluka (e.g. "Andheri", "Kurla", "Borivali")
- district (e.g. "Mumbai", "Mumbai Suburban")

Address: {address}

Return ONLY valid JSON, no markdown, no explanation."""

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", ""),
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.0, max_output_tokens=512),
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            import json

            data = json.loads(json_match.group())
            return {
                "ward": data.get("ward"),
                "village": data.get("village"),
                "taluka": data.get("taluka"),
                "district": data.get("district"),
            }
    except Exception:
        pass
    return {}


async def resolve_tps_scheme(address: str, fp_no: str | None, api_key: str | None = None) -> str | None:
    """
    Use Google Gemini AI to find TPS scheme name for a property.
    """
    import json
    import re

    if not api_key:
        return None

    try:
        client, gtypes = get_genai_client(api_key)

        prompt = f"""Find the TPS (Town Planning Scheme) name for this Mumbai property.
Return ONLY a JSON object with:
- tps_name (e.g. "TPS IV", "TPS No. 2", or null if unknown)

Address: {address}
FP Number: {fp_no or "unknown"}

Return ONLY valid JSON, no markdown, no explanation."""

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", ""),
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.0, max_output_tokens=256),
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            tps = data.get("tps_name")
            if tps and str(tps).lower() not in ("null", "none", ""):
                return tps
    except Exception:
        pass
    return None
