"""
Dhara AI — Agent Runner
Two-phase architecture:
  Phase 1: Deterministic data collection from ALL microservices (parallel groups)
  Phase 2: LLM analyzes collected data → determines eligible schemes → generates reports
"""

import asyncio
import json
import logging
import os
import uuid

from services.orchestrator.agent.llm_client import get_llm_client as get_factory_llm_client
from services.orchestrator.agent.prompts import SYSTEM_PROMPT
from services.orchestrator.agent.tool_executor import tool_executor
from services.orchestrator.agent.tools import TOOLS
from services.orchestrator.db import async_session_factory
from services.orchestrator.models import AuditLog

from dhara_shared.dhara_shared.dhara_common.http import AsyncHTTPClient

logger = logging.getLogger(__name__)

# Module-level LLM client
_llm_client = None

def set_llm_client(client):
    """Injected during app startup."""
    global _llm_client
    _llm_client = client
    if client:
        logger.info("LLM client injected: %s", type(client).__name__)

def get_llm_client():
    """Fail-safe getter to ensure LLM is always available."""
    global _llm_client
    if _llm_client is None:
        logger.warning("LLM client not found. Initializing now...")
        _llm_client = get_factory_llm_client()
    return _llm_client

# ─── LLM Helpers ─────────────────────────────────────────────────────────────

def convert_tools_for_llm(tools: list[dict]) -> list[dict]:
    converted = []
    for t in tools:
        converted.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": t.get("input_schema", {})
        })
    return converted


def parse_llm_response(response: dict):
    choice = response.get("choices", [{}])[0]
    message = choice.get("message", {})
    tool_calls = message.get("tool_calls", [])
    finish_reason = choice.get("finish_reason")
    return tool_calls, finish_reason


# ─── Tool execution helpers ──────────────────────────────────────────────────

_TOOL_TIMEOUTS = {
    "get_pr_card": 600,             # 10 min
    "get_mcgm_property": 300,       # 5 min
    "get_dp_remarks": 300,          # 5 min
    "get_max_height": 600,          # 10 min
    "query_regulations": 300,       # 5 min
    "generate_feasibility_report": 300,
}
_DEFAULT_TIMEOUT = 300

# Keys to strip from results before sending to LLM (binary / large data)
_DROP_KEYS = {
    "raw_data", "raw_attributes", "geometry_wgs84", "nearby_properties",
    "extracted_data", "image_b64", "captcha_image_b64", "screenshot_b64",
    "map_screenshot_b64", "ocr_text", "pr_card_image",
}


async def _call_tool(
    tool_name: str,
    tool_args: dict,
    http: AsyncHTTPClient,
    request_id: str,
    progress_callback=None,
) -> dict:
    """Execute one tool with timeout and audit logging."""
    logger.info("[%s] Calling tool: %s", request_id, tool_name)
    if progress_callback:
        await progress_callback({"type": "tool_call", "tool": tool_name})

    timeout = _TOOL_TIMEOUTS.get(tool_name, _DEFAULT_TIMEOUT)
    try:
        result = await asyncio.wait_for(
            tool_executor.execute_tool(tool_name, tool_args, http),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("[%s] Tool %s timed out after %ds", request_id, tool_name, timeout)
        result = {"error": f"{tool_name} timed out after {timeout}s"}

    status = "success" if isinstance(result, dict) and "error" not in result else "error"
    logger.info("[%s] Tool %s → %s", request_id, tool_name, status)

    # Audit log
    try:
        async with async_session_factory() as db:
            log = AuditLog(
                request_id=request_id,
                action="tool_call",
                tool_name=tool_name,
                input_data=json.loads(json.dumps(tool_args, default=str)),
                output_data=json.loads(json.dumps(result, default=str)) if isinstance(result, dict) else {"raw": str(result)},
                status=status,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.warning("[%s] Audit log failed for %s: %s", request_id, tool_name, e)

    if progress_callback:
        await progress_callback({"type": "tool_result", "tool": tool_name, "success": status == "success"})

    return result


async def _call_tools_parallel(
    calls: list[tuple[str, dict]],
    http: AsyncHTTPClient,
    request_id: str,
    progress_callback=None,
) -> dict[str, dict]:
    """Execute multiple tools in parallel. Returns {tool_name: result}."""
    if not calls:
        return {}
    logger.info("[%s] Running %d tools in parallel: %s", request_id, len(calls), [c[0] for c in calls])

    async def _one(name, args):
        res = await _call_tool(name, args, http, request_id, progress_callback)
        return name, args, res

    completed = await asyncio.gather(*[_one(n, a) for n, a in calls])
    results = {}
    for name, _args, res in completed:
        results[name] = res
    return results


# ─── Main Runner ──────────────────────────────────────────────────────────────

def _map_mcgm_ward(ward: str) -> str:
    """Map standard ward names to MCGM scraper codes."""
    if not ward:
        return ""
    w = ward.strip().upper()
    mapping = {
        "K/EAST": "K/E",
        "K/WEST": "K/W",
        "P/SOUTH": "P/S",
        "P/NORTH": "P/N",
        "R/SOUTH": "R/S",
        "R/CENTRAL": "R/C",
        "R/NORTH": "R/N",
        "H/EAST": "H/E",
        "H/WEST": "H/W",
    }
    # Handle short codes like "K/W" already provided
    for full, short in mapping.items():
        if short in w or full in w:
            return short
    return ward


def _map_rr_location(ward: str) -> tuple[str, str]:
    """Map MCGM ward to Ready Reckoner (District, Taluka)."""
    if not ward:
        return "mumbai", "mumbai-city"
    w = ward.upper()
    # Mumbai City Districts (A to G wards)
    city_wards = [" A ", " B ", " C ", " D ", " E ", " F/S ", " F/N ", " G/S ", " G/N ", "A-", "B-", "C-", "D-", "E-"]
    # Pad ward with spaces for exact matching of single letters
    padded_w = f" {w} "
    for cw in city_wards:
        if cw in padded_w:
            return "mumbai", "mumbai-city"

    # Mumbai Suburban Talukas
    if "H" in w or "K" in w:
        return "mumbai-suburban", "andheri"
    if "P" in w or "R" in w:
        return "mumbai-suburban", "borivali"
    if "L" in w or "M" in w or "N" in w or "S" in w or "T" in w:
        return "mumbai-suburban", "kurla"

    return "mumbai", "mumbai-city"  # Fallback


def _validate_location_inputs(society_data: dict) -> str | None:
    """Return a user-facing error when a request lacks enough location detail."""
    has_address = bool((society_data.get("address") or "").strip())
    has_plot_reference = bool(
        (society_data.get("cts_no") or society_data.get("fp_no") or society_data.get("survey_no") or "").strip()
    )
    has_location_context = bool((society_data.get("ward") or "").strip()) and bool(
        (society_data.get("village") or "").strip()
    )

    if has_address or (has_plot_reference and has_location_context):
        return None

    return "Feasibility analysis needs either a site address or ward + village + CTS/FP/survey details."


async def run_agent(society_data: dict, request_id: str = None, progress_callback=None) -> dict:
    """
    Two-phase agent:
      Phase 1 — Call all microservices deterministically (parallel groups)
      Phase 2 — Send collected data to LLM → it picks schemes → generates reports
    """
    request_id = request_id or str(uuid.uuid4())
    society_name = society_data.get("society_name", "Unnamed Society")
    validation_error = _validate_location_inputs(society_data)
    if validation_error:
        logger.warning("[%s] %s | society=%s", request_id, validation_error, society_name)
        return {
            "status": "error",
            "error": validation_error,
            "summary": validation_error,
            "report_path": None,
            "all_reports": [],
            "reports_count": 0,
            "tool_calls": 0,
            "tool_log": [],
            "llm_client": "N/A",
            "model": "N/A",
            "request_id": request_id,
        }
    logger.info("[%s] Starting feasibility analysis for %s", request_id, society_name)

    tool_results_log = []  # [{tool, input, result}, ...]
    collected = {}         # {tool_name: result_dict}
    report_paths = []

    async with AsyncHTTPClient(request_id=request_id) as http:
        # ══════════════════════════════════════════════════════════════
        # PHASE 1: Deterministic data collection from all microservices
        # ══════════════════════════════════════════════════════════════

        if progress_callback:
            await progress_callback({"type": "phase", "phase": "data_collection"})

        # ── PR Card — fire-and-forget (runs in background, doesn't block) ──
        # PR card takes 2-5 minutes (CAPTCHA solving). We start it now and
        # collect the result at the end if it finishes in time.
        pr_card_task = None
        pr_card_args = None
        if all(society_data.get(k) for k in ("district", "taluka", "village", "survey_no")):
            pr_card_args = {
                "district": society_data["district"],
                "taluka": society_data["taluka"],
                "village": society_data["village"],
                "survey_no": society_data["survey_no"],
                "record_of_right": "Property Card",
            }
            logger.info("[%s] Starting PR card in background (up to 5 min)", request_id)
            pr_card_task = asyncio.create_task(
                _call_tool("get_pr_card", pr_card_args, http, request_id, progress_callback)
            )

        # ── GROUP 1 (parallel): MCGM Property + Site Analysis ──

        group1_calls = []

        # MCGM Property — needs ward, village, cts_no
        if society_data.get("ward") and society_data.get("village") and society_data.get("cts_no") and "get_mcgm_property" not in collected:
            # Ensure ward is mapped correctly (e.g. K/East -> K/E)

            mapped_ward = _map_mcgm_ward(society_data["ward"])

            # Scraper works best with a single CTS at a time
            cts_no = society_data["cts_no"]
            if "," in cts_no:
                cts_no = cts_no.split(",")[0].strip()
            elif " " in cts_no.strip():
                cts_no = cts_no.strip().split(" ")[0].strip()

            group1_calls.append(("get_mcgm_property", {
                "ward": mapped_ward,
                "village": society_data["village"],
                "cts_no": cts_no,
                "include_nearby": True,
            }))

        # Site Analysis — needs address
        if society_data.get("address"):
            group1_calls.append(("analyse_site", {
                "address": society_data["address"],
                "ward": society_data.get("ward", ""),
                "plot_no": society_data.get("cts_no", ""),
            }))

        g1 = await _call_tools_parallel(group1_calls, http, request_id, progress_callback)
        collected.update(g1)
        for name in g1:
            tool_results_log.append({"tool": name, "input": dict(next(a for n, a in group1_calls if n == name)), "result": g1[name]})

        # Extract coordinates for Group 2
        mcgm = collected.get("get_mcgm_property", {})
        site = collected.get("analyse_site", {})
        lat = mcgm.get("centroid_lat") or site.get("lat")
        lng = mcgm.get("centroid_lng") or site.get("lng")

        # ── GROUP 2 (parallel): DP Remarks + Max Height ──
        group2_calls = []

        # DP Remarks — needs ward, village, and CTS or FP number
        # Use FP if cts_validated indicates DP 2034 scheme, otherwise use CTS
        if society_data.get("ward") and society_data.get("village") and "get_dp_remarks" not in collected:
            cts_no = society_data.get("cts_no") or society_data.get("fp_no")
            fp_no = society_data.get("fp_no")

            # Determine which number to use based on validation status
            cts_validated = society_data.get("cts_validated", "")
            use_fp = cts_validated in ("true", "false", "dp2034", "dp1991") and fp_no

            search_number = fp_no if use_fp else cts_no

            if search_number:
                mapped_ward = _map_mcgm_ward(society_data["ward"])
                dp_args = {
                    "ward": mapped_ward,
                    "village": society_data["village"],
                    "cts_no": search_number,  # Can be CTS or FP depending on scheme
                    "use_fp_scheme": use_fp,  # Tell DP service to search as FP
                }
                if lat and lng:
                    dp_args["lat"] = lat
                    dp_args["lng"] = lng
                group2_calls.append(("get_dp_remarks", dp_args))

        # Max Height — needs lat/lng
        if lat and lng:
            group2_calls.append(("get_max_height", {
                "lat": lat,
                "lng": lng,
                "site_elevation": 0,
            }))

        g2 = await _call_tools_parallel(group2_calls, http, request_id, progress_callback)
        collected.update(g2)
        for name in g2:
            tool_results_log.append({"tool": name, "input": dict(next(a for n, a in group2_calls if n == name)), "result": g2[name]})

        # ── GROUP 3 (parallel): Regulations + Premiums ──
        dp_report = collected.get("get_dp_remarks", {})
        plot_sqm = mcgm.get("area_sqm") or society_data.get("plot_area_sqm") or 0

        # ── Fallback: Estimate plot area from carpet area if missing ──────────
        if not plot_sqm and society_data.get("residential_area_sqft"):
            # Existing Carpet / 0.8 (efficiency) / 1.33 (avg base FSI in Mumbai)
            carpet_sqft = float(society_data["residential_area_sqft"])
            est_plot_sqft = (carpet_sqft / 0.75) / 1.33
            plot_sqm = round(est_plot_sqft / 10.764, 2)
            logger.info("[%s] Estimated plot area from carpet: %.2f sqm", request_id, plot_sqm)

        road_width = dp_report.get("road_width_m") or society_data.get("road_width_m", 9)

        # Compute BUA estimates for premium calculation
        total_fsi = 4.0  # conservative default
        plot_sqft = float(plot_sqm) * 10.764
        permissible_bua = plot_sqft * total_fsi

        group3_calls = []
        requested_scheme = society_data.get("scheme") or "33(20)(B)"

        # Query Regulations — adapt query based on collected data
        ward = society_data.get("ward", "")
        zone_code = dp_report.get("zone_code") or "residential"

        # ── Intelligence: Estimate missing society metrics ──────────────────
        num_flats = society_data.get("num_flats") or 0
        if not num_flats and society_data.get("residential_area_sqft"):
            # Estimate flats based on ~750 sqft avg
            num_flats = max(1, int(float(society_data["residential_area_sqft"]) / 750))
            logger.info("[%s] Estimated %d flats from carpet area", request_id, num_flats)

        num_commercial = society_data.get("num_commercial", 0)
        property_type = "mixed-use" if num_commercial else "residential"
        plot_size_desc = "large cluster" if float(plot_sqm) >= 4000 else "society"

        rag_query = (
            f"DCPR 2034 eligible redevelopment schemes for {property_type} {plot_size_desc} "
            f"in ward {ward}, zone {zone_code}, plot area {plot_sqm} sqm, "
            f"road width {road_width}m. "
            f"Include FSI incentives, premium percentages, TDR eligibility, "
            f"and conditions for 30(A), 33(7)(A), 33(7)(B), 33(9), 33(12)(B), 33(19), 33(20)(B)."
        )
        group3_calls.append(("query_regulations", {
            "query": rag_query,
            "scheme": requested_scheme,
        }))

        # Calculate Premiums
        locality = (society_data.get("village") or "").strip().lower()
        if not locality:
            locality = (society_data.get("address") or "").strip().lower()

        rr_dist, rr_tal = _map_rr_location(society_data.get("ward", ""))
        rr_zone = (society_data.get("rr_zone") or "").strip()
        premium_skip_error = None

        if rr_zone and locality:
            group3_calls.append(("calculate_premiums", {
                "district": society_data.get("district") or rr_dist,
                "taluka": society_data.get("taluka") or rr_tal,
                "locality": locality,
                "zone": rr_zone,
                "sub_zone": "",
                "scheme": requested_scheme,
                "property_type": "residential",
                "plot_area_sqm": plot_sqm,
                "permissible_bua_sqft": permissible_bua,
                "residential_bua_sqft": permissible_bua * 0.7,
                "commercial_bua_sqft": permissible_bua * 0.3,
                "fungible_residential_sqft": permissible_bua * 0.7 * 0.35,
                "premium_fsi_ratio": 0.50,
            }))
        else:
            premium_skip_error = (
                "Ready Reckoner lookup skipped: missing rr_zone or locality context."
            )
            logger.warning("[%s] %s", request_id, premium_skip_error)

        g3 = await _call_tools_parallel(group3_calls, http, request_id, progress_callback)
        collected.update(g3)
        for name in g3:
            tool_results_log.append({"tool": name, "input": dict(next(a for n, a in group3_calls if n == name)), "result": g3[name]})
        if premium_skip_error:
            skipped = {"error": premium_skip_error}
            collected["calculate_premiums"] = skipped
            tool_results_log.append(
                {
                    "tool": "calculate_premiums",
                    "input": {"rr_zone": rr_zone, "locality": locality},
                    "result": skipped,
                }
            )

        # Extract legal citations from regulations
        legal_citations = []
        reg_result = collected.get("query_regulations", {})
        for s in reg_result.get("sources", []):
            legal_citations.append({
                "clause": s.get("source", "DCPR 2034"),
                "text": s.get("text", "")[:500],
            })

        # ── Collect PR Card result (if it finished by now) ──
        if pr_card_task:
            if pr_card_task.done():
                pr_result = pr_card_task.result()
                logger.info("[%s] PR card completed in time", request_id)
            else:
                # Give it 30 more seconds — Groups 1-3 already took ~60-90s
                logger.info("[%s] PR card still running, waiting up to 30s more...", request_id)
                try:
                    pr_result = await asyncio.wait_for(pr_card_task, timeout=30)
                    logger.info("[%s] PR card completed after extra wait", request_id)
                except TimeoutError:
                    logger.warning("[%s] PR card still not done — continuing without it", request_id)
                    pr_result = {"error": "PR card still processing — will be available later"}
                    # Don't cancel — let it finish in background for audit logging
            collected["get_pr_card"] = pr_result
            tool_results_log.append({"tool": "get_pr_card", "input": pr_card_args, "result": pr_result})

        # ══════════════════════════════════════════════════════════════
        # PHASE 2: LLM analyzes data → determines schemes → generates reports
        # ══════════════════════════════════════════════════════════════

        if progress_callback:
            await progress_callback({"type": "phase", "phase": "llm_analysis"})

        # Build a summary of all collected data for the LLM
        # Sanitize collected data first — some services return non-serializable objects
        safe_collected = json.loads(json.dumps(collected, default=str))
        data_summary = _build_data_summary(society_data, safe_collected)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"All microservice data has been collected. Here is the complete data:\n\n"
                f"{json.dumps(data_summary, indent=2, default=str)}\n\n"
                f"Now determine which schemes are eligible for this property and call "
                f"generate_feasibility_report for EACH eligible (scheme, redevelopment_type) "
                f"combination. Call them ALL IN A SINGLE RESPONSE so they run in parallel."
            )},
        ]

        # Only give LLM the report generation tool — data collection is done
        report_tool = [t for t in TOOLS if t["name"] == "generate_feasibility_report"]
        converted_report_tool = convert_tools_for_llm(report_tool)

        # Give LLM up to 3 iterations to generate reports
        for iteration in range(3):
            logger.info("[%s] LLM iteration %d/3", request_id, iteration + 1)

            try:
                llm = get_llm_client()
                if not llm:
                    logger.error("[%s] No LLM available.", request_id)
                    break

                # Sanitize messages — some service responses contain non-JSON-serializable
                # objects (e.g. PostGIS MapComposite) that leak into the conversation
                safe_messages = json.loads(json.dumps(messages, default=str))
                response = await llm.chat(
                    messages=safe_messages, tools=converted_report_tool, max_tokens=8192,
                )
                choice = response.get("choices", [{}])[0]
                assistant_msg = choice.get("message", {})
                messages.append(assistant_msg)

            except Exception as e:
                import traceback
                logger.error("[%s] LLM call failed: %s\n%s", request_id, e, traceback.format_exc())
                break

            tool_calls, finish_reason = parse_llm_response(response)

            if not tool_calls:
                if not report_paths:
                    logger.info("[%s] LLM didn't call report tool (iter %d). Nudging.", request_id, iteration + 1)
                    messages.append({
                        "role": "user",
                        "content": (
                            "You MUST call generate_feasibility_report NOW. At minimum, "
                            "call it with scheme='33(20)(B)' and redevelopment_type='CLUBBING'. "
                            "ONLY respond with tool calls, no text."
                        ),
                    })
                    continue
                break

            # Execute all report generation calls in parallel
            report_calls = []
            for tc in tool_calls:
                if "function" in tc:
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                else:
                    tool_name = tc.get("name")
                    tool_args = tc.get("arguments", tc.get("input", {}))

                if tool_name == "generate_feasibility_report":
                    # Inject microservice data the LLM may not have included
                    tool_args = _enrich_report_args(tool_args, society_data, collected, legal_citations)
                    report_calls.append((tc, tool_name, tool_args))

            if report_calls:
                logger.info("[%s] Generating %d reports in parallel", request_id, len(report_calls))

                async def _gen_one(tc_tuple):
                    tc, name, args = tc_tuple
                    res = await _call_tool(name, args, http, request_id, progress_callback)
                    return tc, name, args, res

                completed = await asyncio.gather(*[_gen_one(rc) for rc in report_calls])

                for tc, tool_name, tool_args, result in completed:
                    tool_results_log.append({"tool": tool_name, "input": tool_args, "result": result})
                    path = result.get("path")
                    if path:
                        report_paths.append({
                            "path": path,
                            "scheme": tool_args.get("scheme", "unknown"),
                            "redevelopment_type": tool_args.get("redevelopment_type", "CLUBBING"),
                        })

                    # Feed result back to LLM
                    result_str = json.dumps(result, default=str)
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "..."
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "none"),
                        "name": tool_name,
                        "content": result_str,
                    })

            if report_paths:
                break

        # ── Fallback: if LLM never generated a report, force one ─────
        if not report_paths:
            logger.warning("[%s] LLM failed to generate any reports. Force-calling with 33(20)(B).", request_id)
            forced_args = _enrich_report_args(
                {"scheme": "33(20)(B)", "redevelopment_type": "CLUBBING"},
                society_data, collected, legal_citations,
            )
            result = await _call_tool("generate_feasibility_report", forced_args, http, request_id, progress_callback)
            tool_results_log.append({"tool": "generate_feasibility_report", "input": forced_args, "result": result})
            path = result.get("path")
            if path:
                report_paths.append({"path": path, "scheme": "33(20)(B)", "redevelopment_type": "CLUBBING"})

    # ── Extract LLM summary ──────────────────────────────────────────
    final_summary = "Analysis Complete."
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [p.get("text", "") for p in content if p.get("type") == "text"]
                if texts:
                    final_summary = " ".join(texts)
                    break
            elif isinstance(content, str) and content.strip():
                final_summary = content
                break

    # ── Audit log ────────────────────────────────────────────────────
    report_path = report_paths[0]["path"] if report_paths else None
    try:
        async with async_session_factory() as db:
            final_log = AuditLog(
                request_id=request_id,
                action="analysis_complete",
                message=final_summary[:2000],
                output_data={
                    "tool_calls_count": len(tool_results_log),
                    "report_path": report_path,
                    "all_reports": report_paths,
                }
            )
            db.add(final_log)
            await db.commit()
    except Exception as e:
        logger.warning("[%s] Final audit log failed: %s", request_id, e)

    llm = get_llm_client()
    return {
        "status": "success" if report_paths else "completed_without_report",
        "summary": final_summary,
        "report_path": report_path,
        "all_reports": report_paths,
        "reports_count": len(report_paths),
        "tool_calls": len(tool_results_log),
        "tool_log": tool_results_log,
        "llm_client": type(llm).__name__ if llm else "N/A",
        "model": llm.get_model_name() if llm else "N/A",
        "request_id": request_id,
    }


# ─── Helper functions ────────────────────────────────────────────────────────

def _build_data_summary(society_data: dict, collected: dict) -> dict:
    """Build a concise summary of all collected data for the LLM."""

    # ── Intelligence: Extract and Estimate scalar metrics ────────────────
    plot_sqm = society_data.get("plot_area_sqm") or collected.get("get_mcgm_property", {}).get("area_sqm") or 0
    carpet_sqft = float(society_data.get("residential_area_sqft") or 0)

    if not plot_sqm and carpet_sqft:
        # Estimate plot area from carpet (assuming ZONAL_FSI and 0.75 efficiency)
        zonal_fsi = float(os.getenv("ZONAL_FSI", 1.33))
        plot_sqm = round((carpet_sqft / 0.75) / zonal_fsi / 10.764, 2)

    num_flats = society_data.get("num_flats") or 0
    if not num_flats and carpet_sqft:
        num_flats = max(1, int(carpet_sqft / 750))

    sale_rate = society_data.get("sale_rate") or 60000

    summary = {
        "society": {
            "name": society_data.get("society_name"),
            "address": society_data.get("address"),
            "ward": society_data.get("ward"),
            "village": society_data.get("village"),
            "plot_area_sqm": plot_sqm,
            "road_width_m": society_data.get("road_width_m") or collected.get("get_dp_remarks", {}).get("road_width_m") or 9,
            "num_flats": num_flats,
            "num_commercial": society_data.get("num_commercial") or 0,
            "residential_area_sqft": carpet_sqft,
            "commercial_area_sqft": society_data.get("commercial_area_sqft") or 0,
            "sale_rate": sale_rate,
        },
    }

    # MCGM Property
    mcgm = collected.get("get_mcgm_property", {})
    if mcgm and "error" not in mcgm:
        summary["mcgm_property"] = {
            "area_sqm": mcgm.get("area_sqm"),
            "tps_name": mcgm.get("tps_name"),
            "fp_no": mcgm.get("fp_no"),
            "centroid": f"{mcgm.get('centroid_lat')},{mcgm.get('centroid_lng')}",
            "status": mcgm.get("status"),
        }

    # DP Report
    dp = collected.get("get_dp_remarks", {})
    if dp and "error" not in dp:
        summary["dp_report"] = {
            "report_type": dp.get("report_type"),
            "reference_no": dp.get("reference_no"),
            "report_date": dp.get("report_date"),
            "fp_no": dp.get("fp_no"),
            "tps_name": dp.get("tps_name"),
            "zone_code": dp.get("zone_code"),
            "zone_name": dp.get("zone_name"),
            "road_width_m": dp.get("road_width_m"),
            "fsi": dp.get("fsi"),
            "dp_roads": dp.get("dp_roads"),
            "proposed_road": dp.get("proposed_road"),
            "proposed_road_widening": dp.get("proposed_road_widening"),
            "rl_remarks_traffic": dp.get("rl_remarks_traffic"),
            "rl_remarks_survey": dp.get("rl_remarks_survey"),
            "water_pipeline": dp.get("water_pipeline"),
            "sewer_line": dp.get("sewer_line"),
            "ground_level": dp.get("ground_level"),
            "crz_zone": dp.get("crz_zone"),
            "heritage_zone": dp.get("heritage_zone"),
            "reservations": dp.get("reservations"),
            "ep_nos": dp.get("ep_nos"),
            "sm_nos": dp.get("sm_nos"),
            "dp_remarks": dp.get("dp_remarks"),
        }

    # Site Analysis
    site = collected.get("analyse_site", {})
    if site and "error" not in site:
        summary["site_analysis"] = {
            "lat": site.get("lat"),
            "lng": site.get("lng"),
            "formatted_address": site.get("formatted_address"),
            "area_type": site.get("area_type"),
        }

    # Max Height
    height = collected.get("get_max_height", {})
    if height and "error" not in height:
        summary["max_height"] = {
            "max_height_m": height.get("max_height_m"),
            "max_floors": height.get("max_floors"),
            "aai_zone": height.get("aai_zone"),
        }

    # PR Card
    pr = collected.get("get_pr_card", {})
    if pr and "error" not in pr:
        summary["pr_card"] = {
            "status": pr.get("status"),
            "download_url": pr.get("download_url"),
            "tenure": pr.get("tenure"),
            "assessment": pr.get("assessment"),
        }

    # Regulations
    reg = collected.get("query_regulations", {})
    if reg and "error" not in reg:
        answer = str(reg.get("answer", ""))
        summary["regulations"] = {
            "answer": answer[:500] if len(answer) > 500 else answer,
            "sources_count": len(reg.get("sources", [])),
        }

    # Premiums
    prem = collected.get("calculate_premiums", {})
    if prem and "error" not in prem:
        # Extract RR rates from the list format returned by premium service
        rr_land = None
        rr_res = None
        for item in (prem.get("rr_rates") or []):
            cat = str(item.get("category", "")).lower()
            if "land" in cat or "open" in cat:
                rr_land = item.get("value")
            elif "resid" in cat:
                rr_res = item.get("value")
        summary["premiums"] = {
            "grand_total_crore": prem.get("grand_total_crore"),
            "grand_total": prem.get("grand_total"),
            "rr_residential_sqm": rr_res,
            "rr_open_land_sqm": rr_land,
        }

    # Errors
    errors = {name: res.get("error") for name, res in collected.items() if isinstance(res, dict) and "error" in res}
    if errors:
        summary["service_errors"] = errors

    return summary


def _enrich_report_args(
    args: dict,
    society_data: dict,
    collected: dict,
    legal_citations: list,
) -> dict:
    """Ensure report args have all required fields from society + microservice data."""
    enriched = dict(args)

    # Society scalars
    enriched.setdefault("society_name", society_data.get("society_name", "Society"))

    # Estimate plot area if missing
    p_sqm = society_data.get("plot_area_sqm") or collected.get("get_mcgm_property", {}).get("area_sqm") or 0
    if not p_sqm and society_data.get("residential_area_sqft"):
         p_sqm = round((float(society_data["residential_area_sqft"]) / 0.75) / 1.33 / 10.764, 2)
    enriched.setdefault("plot_area_sqm", p_sqm)

    enriched.setdefault("road_width_m", society_data.get("road_width_m") or collected.get("get_dp_remarks", {}).get("road_width_m") or 9)

    # Estimate flats if missing
    n_flats = society_data.get("num_flats") or 0
    if not n_flats and society_data.get("residential_area_sqft"):
        n_flats = max(1, int(float(society_data["residential_area_sqft"]) / 750))
    enriched.setdefault("num_flats", n_flats)

    enriched.setdefault("num_commercial", society_data.get("num_commercial", 0))
    enriched.setdefault("existing_residential_carpet_sqft", society_data.get("residential_area_sqft", 0))
    enriched.setdefault("existing_commercial_carpet_sqft", society_data.get("commercial_area_sqft", 0))
    enriched["sale_rate_per_sqft"] = args.get("sale_rate_per_sqft") or society_data.get("sale_rate") or 60000
    enriched.setdefault("ward", society_data.get("ward", ""))
    enriched.setdefault("redevelopment_type", "CLUBBING")
    enriched.setdefault("regulatory_sources", legal_citations)

    # Pass through UI overrides
    enriched.setdefault("manual_inputs", society_data.get("manual_inputs", {}))
    enriched.setdefault("financial", society_data.get("financial", {}))

    # Inject full microservice responses (sanitized to be JSON-safe)
    _tool_to_key = {
        "get_mcgm_property": "mcgm_property",
        "get_dp_remarks": "dp_report",
        "analyse_site": "site_analysis",
        "get_max_height": "height",
        "calculate_premiums": "premium",
        "query_regulations": "zone_regulations",
    }
    for tool_name, arg_key in _tool_to_key.items():
        res = collected.get(tool_name, {})
        if isinstance(res, dict) and "error" not in res:
            safe_res = json.loads(json.dumps(res, default=str))
            enriched.setdefault(arg_key, safe_res)

    # Ready reckoner rates from premium response
    # The premium service returns rr_rates as a LIST: [{"category": "Land", "value": 147320}, ...]
    # The cell mapper expects ready_reckoner.rr_open_land_sqm and ready_reckoner.rr_residential_sqm
    # Also premium.rr_open_land_sqm and premium.rr_residential_sqm
    prem = collected.get("calculate_premiums", {})
    if prem and "error" not in prem:
        rr_rates_list = prem.get("rr_rates", [])
        rr_dict = {}
        if isinstance(rr_rates_list, list):
            for item in rr_rates_list:
                cat = str(item.get("category", "")).lower()
                val = item.get("value", 0)
                if "land" in cat or "open" in cat:
                    rr_dict["rr_open_land_sqm"] = val
                elif "resid" in cat or "flat" in cat:
                    rr_dict["rr_residential_sqm"] = val
                elif "commerc" in cat or "shop" in cat or "office" in cat:
                    rr_dict["rr_commercial_sqm"] = val

        # Merge location info
        matched = prem.get("matched_location") or {}
        rr_dict.update({k: v for k, v in matched.items() if k not in rr_dict})

        if rr_dict:
            enriched.setdefault("ready_reckoner", rr_dict)
            # Also inject into the premium dict so premium.rr_open_land_sqm resolves
            if "premium" in enriched and isinstance(enriched["premium"], dict):
                enriched["premium"].setdefault("rr_open_land_sqm", rr_dict.get("rr_open_land_sqm"))
                enriched["premium"].setdefault("rr_residential_sqm", rr_dict.get("rr_residential_sqm"))

    # Final sanitization — ensure no protobuf/PostGIS objects leak to report generator
    return json.loads(json.dumps(enriched, default=str))



