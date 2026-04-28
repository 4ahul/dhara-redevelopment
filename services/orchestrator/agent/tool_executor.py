"""
Dhara AI — Tool Executor
HTTP dispatcher: routes tool calls to downstream microservices.
"""

import asyncio
import json
import logging
import os

import httpx

from services.orchestrator.core.config import settings

logger = logging.getLogger(__name__)

# ── Service URL Mapping ──────────────────────────────────────────────────────

TOOL_URL_MAP = {
    "analyse_site": (settings.SITE_ANALYSIS_URL, "/analyse"),
    "get_max_height": (settings.HEIGHT_URL, "/check-height"),
    "calculate_premiums": (settings.PREMIUM_URL, "/calculate"),
    "generate_feasibility_report": (settings.REPORT_URL, "/generate/template"),
    "query_regulations": (settings.RAG_URL, "/api/query"),
    "get_pr_card": (settings.PR_CARD_URL, "/scrape"),
    "get_mcgm_property": (settings.MCGM_PROPERTY_URL, "/lookup"),
    "get_dp_remarks": (settings.DP_REPORT_URL, "/fetch"),
}

# How long to wait for async jobs to complete via polling
_PR_CARD_POLL_INTERVAL = 3  # seconds between status checks
_PR_CARD_POLL_TIMEOUT = 180  # max total seconds to wait
_MCGM_POLL_INTERVAL = 3  # seconds between status checks
_MCGM_POLL_TIMEOUT = 120  # max total seconds to wait
_DP_POLL_INTERVAL = 3  # seconds between status checks
_DP_POLL_TIMEOUT = 120  # max total seconds to wait


class ToolExecutor:
    """Dispatches agent tool calls to microservices over HTTP."""

    # ── Redis cache for expensive lookups ─────────────────────────────────
    _CACHEABLE_TOOLS = {"get_mcgm_property", "get_pr_card", "analyse_site", "get_max_height"}
    _CACHE_TTL = 3600 * 24  # 24 hours

    def _cache_key(self, tool_name: str, tool_args: dict) -> str:
        """Stable cache key from tool name + sorted args."""
        import hashlib

        arg_str = json.dumps(tool_args, sort_keys=True, default=str)
        h = hashlib.md5(f"{tool_name}:{arg_str}".encode()).hexdigest()
        return f"tool_cache:{tool_name}:{h}"

    async def _get_cached(self, key: str):
        try:
            from services.orchestrator.services.redis import get_redis

            r = get_redis()
            if r:
                data = r.get(key)
                if data:
                    return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cached(self, key: str, result: dict):
        try:
            from services.orchestrator.services.redis import get_redis

            r = get_redis()
            if r and "error" not in result:
                r.setex(key, self._CACHE_TTL, json.dumps(result, default=str))
        except Exception:
            pass

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: dict,
        http_client: httpx.AsyncClient,
    ) -> dict:
        # Check cache for expensive lookups
        if tool_name in self._CACHEABLE_TOOLS:
            cache_key = self._cache_key(tool_name, tool_args)
            cached = await self._get_cached(cache_key)
            if cached:
                logger.info("Cache HIT for %s", tool_name)
                return cached

        result = await self._execute_tool_inner(tool_name, tool_args, http_client)

        # Cache successful results
        if (
            tool_name in self._CACHEABLE_TOOLS
            and isinstance(result, dict)
            and "error" not in result
        ):
            await self._set_cached(self._cache_key(tool_name, tool_args), result)

        return result

    async def _execute_tool_inner(
        self,
        tool_name: str,
        tool_args: dict,
        http_client: httpx.AsyncClient,
    ) -> dict:
        if tool_name == "get_pr_card":
            return await self._execute_pr_card(tool_args, http_client)

        if tool_name == "get_mcgm_property":
            return await self._execute_mcgm_property(tool_args, http_client)

        if tool_name == "get_dp_remarks":
            return await self._execute_dp_report(tool_args, http_client)

        if tool_name not in TOOL_URL_MAP:
            return {"error": f"Unknown tool: {tool_name}"}

        base_url, path = TOOL_URL_MAP[tool_name]
        url = f"{base_url}{path}"

        try:
            # Use longer timeout for RAG queries (Zilliz init + embedding + LLM)
            req_timeout = 120.0 if tool_name == "query_regulations" else 60.0
            response = await http_client.post(url, json=tool_args, timeout=req_timeout)
            response.raise_for_status()

            ct = response.headers.get("content-type", "")
            if "pdf" in ct:
                return self._save_report(response, ext="pdf")
            if "spreadsheetml" in ct:
                return self._save_report(response, ext="xlsx")

            raw = response.json()
            # If the response is wrapped in InternalServiceResponse, unwrap it
            if isinstance(raw, dict) and "status" in raw and "data" in raw:
                # If it's a success, return just the data
                if raw["status"] == "success":
                    return raw["data"]
                # If it's an error, return the error message
                if raw["status"] == "error":
                    return {"error": raw.get("error") or "Service returned error status"}

            return raw

        except httpx.TimeoutException:
            logger.error("Tool %s timed out at %s", tool_name, url)
            return {"error": f"{tool_name} timed out"}
        except httpx.HTTPStatusError as e:
            logger.error(
                "Tool %s HTTP %d: %s", tool_name, e.response.status_code, e.response.text[:200]
            )
            # Parse structured error body from our services (503s return JSON with detail)
            try:
                err_body = e.response.json().get("detail", {})
                if isinstance(err_body, dict):
                    return {
                        "error": err_body.get(
                            "message", f"{tool_name} returned {e.response.status_code}"
                        ),
                        "status_code": e.response.status_code,
                        "suggestion": err_body.get("suggestion", ""),
                    }
            except Exception:
                pass
            return {
                "error": f"{tool_name} returned {e.response.status_code}",
                "detail": e.response.text[:500],
            }
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            return {"error": str(e)}

    # ── PR Card: submit → poll → return ─────────────────────────────────────

    async def _execute_pr_card(self, tool_args: dict, http_client: httpx.AsyncClient) -> dict:
        """
        Submit a PR Card request and poll /status/{pr_id} until completion.
        This is more resilient than a single long-lived HTTP connection:
          - Scraping continues in the background even if a poll call fails
          - Each poll is a short, cheap GET request
          - The orchestrator stays responsive (not blocked on one long POST)
        """
        base_url, _ = TOOL_URL_MAP["get_pr_card"]
        submit_url = f"{base_url}/scrape"
        status_base = f"{base_url}/status"

        # 1. Submit the job
        try:
            resp = await http_client.post(submit_url, json=tool_args, timeout=15.0)
            resp.raise_for_status()
            job = resp.json()
        except httpx.TimeoutException:
            return {"error": "PR Card service did not respond to submit request"}
        except httpx.HTTPStatusError as e:
            return {
                "error": f"PR Card submit failed: HTTP {e.response.status_code}",
                "detail": e.response.text[:500],
            }
        except Exception as e:
            return {"error": f"PR Card submit error: {e}"}

        pr_id = job.get("id")
        if not pr_id:
            # Unexpected response — return as-is
            return job

        logger.info("PR Card job submitted: pr_id=%s", pr_id)

        # 2. Poll until terminal status
        elapsed = 0
        while elapsed < _PR_CARD_POLL_TIMEOUT:
            await asyncio.sleep(_PR_CARD_POLL_INTERVAL)
            elapsed += _PR_CARD_POLL_INTERVAL

            try:
                poll = await http_client.get(f"{status_base}/{pr_id}", timeout=10.0)
                poll.raise_for_status()
                data = poll.json()
            except Exception as e:
                logger.warning("PR Card poll failed (will retry): %s", e)
                continue

            status = data.get("status")
            logger.info("PR Card %s — status: %s (%ds elapsed)", pr_id, status, elapsed)

            if status == "completed":
                return data

            if status in ("failed", "captcha_required"):
                # captcha_required means auto-solver exhausted all retries — treat as failure.
                # CAPTCHA is the service's internal concern; the orchestrator just retries.
                return {
                    "error": data.get("error_message", "PR Card extraction failed"),
                    "pr_id": pr_id,
                    "status": "failed",
                }

            # status == "processing" → keep polling

        return {
            "error": f"PR Card extraction timed out after {_PR_CARD_POLL_TIMEOUT}s",
            "pr_id": pr_id,
        }

    # ── MCGM Property: submit → poll → return ───────────────────────────────

    async def _execute_mcgm_property(self, tool_args: dict, http_client: httpx.AsyncClient) -> dict:
        """
        Submit a MCGM property lookup request and poll /status/{id} until completion.
        Uses the same polling pattern as _execute_pr_card for resilience.
        """
        base_url, _ = TOOL_URL_MAP["get_mcgm_property"]
        submit_url = f"{base_url}/lookup"
        status_base = f"{base_url}/status"

        # 1. Submit the job
        try:
            resp = await http_client.post(submit_url, json=tool_args, timeout=15.0)
            resp.raise_for_status()
            job = resp.json()
        except httpx.TimeoutException:
            return {"error": "MCGM property lookup service did not respond to submit request"}
        except httpx.HTTPStatusError as e:
            return {
                "error": f"MCGM property lookup submit failed: HTTP {e.response.status_code}",
                "detail": e.response.text[:500],
            }
        except Exception as e:
            return {"error": f"MCGM property lookup submit error: {e}"}

        lookup_id = job.get("id")
        if not lookup_id:
            return job

        logger.info("MCGM property lookup job submitted: id=%s", lookup_id)

        # 2. Poll until terminal status
        elapsed = 0
        while elapsed < _MCGM_POLL_TIMEOUT:
            await asyncio.sleep(_MCGM_POLL_INTERVAL)
            elapsed += _MCGM_POLL_INTERVAL

            try:
                poll = await http_client.get(f"{status_base}/{lookup_id}", timeout=10.0)
                poll.raise_for_status()
                data = poll.json()
            except Exception as e:
                logger.warning("MCGM property lookup poll failed (will retry): %s", e)
                continue

            status = data.get("status")
            logger.info(
                "MCGM property lookup %s — status: %s (%ds elapsed)",
                lookup_id,
                status,
                elapsed,
            )

            if status == "completed":
                return data

            if status == "failed":
                return {
                    "error": data.get("error_message", "MCGM property lookup failed"),
                    "lookup_id": lookup_id,
                    "status": "failed",
                }

            # status == "processing" → keep polling

        return {
            "error": f"MCGM property lookup timed out after {_MCGM_POLL_TIMEOUT}s",
            "lookup_id": lookup_id,
        }

    # ── DP Report: submit → poll → return ──────────────────────────────────

    async def _execute_dp_report(self, tool_args: dict, http_client: httpx.AsyncClient) -> dict:
        """
        Submit a DP remarks request and poll /status/{id} until completion.
        """
        base_url, _ = TOOL_URL_MAP["get_dp_remarks"]
        submit_url = f"{base_url}/fetch"
        status_base = f"{base_url}/status"

        # 1. Submit the job
        try:
            resp = await http_client.post(submit_url, json=tool_args, timeout=15.0)
            resp.raise_for_status()
            job = resp.json()
        except httpx.TimeoutException:
            return {"error": "DP report service did not respond to submit request"}
        except httpx.HTTPStatusError as e:
            return {
                "error": f"DP report submit failed: HTTP {e.response.status_code}",
                "detail": e.response.text[:500],
            }
        except Exception as e:
            return {"error": f"DP report submit error: {e}"}

        report_id = job.get("id")
        if not report_id:
            return job

        logger.info("DP report job submitted: id=%s", report_id)

        # 2. Poll until terminal status
        elapsed = 0
        while elapsed < _DP_POLL_TIMEOUT:
            await asyncio.sleep(_DP_POLL_INTERVAL)
            elapsed += _DP_POLL_INTERVAL

            try:
                poll = await http_client.get(f"{status_base}/{report_id}", timeout=10.0)
                poll.raise_for_status()
                data = poll.json()
            except Exception as e:
                logger.warning("DP report poll failed (will retry): %s", e)
                continue

            status = data.get("status")
            logger.info("DP report %s — status: %s (%ds elapsed)", report_id, status, elapsed)

            if status == "completed":
                return data

            if status == "failed":
                return {
                    "error": data.get("error_message", "DP report fetch failed"),
                    "report_id": report_id,
                    "status": "failed",
                }

        return {
            "error": f"DP report fetch timed out after {_DP_POLL_TIMEOUT}s",
            "report_id": report_id,
        }

    # ── Binary report helper (PDF or Excel) ──────────────────────────────────

    def _save_report(self, response: httpx.Response, ext: str = "pdf") -> dict:
        import uuid

        disposition = response.headers.get("content-disposition", "")
        if "filename=" in disposition:
            filename = disposition.split("filename=")[-1].strip('"')
        else:
            filename = f"report_{uuid.uuid4().hex[:8]}.{ext}"
        out_dir = getattr(settings, "REPORT_OUTPUT_DIR", "/tmp/reports")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        with open(out_path, "wb") as f:
            f.write(response.content)
        return {"status": "success", "message": "Report generated", "path": out_path, "format": ext}


tool_executor = ToolExecutor()
