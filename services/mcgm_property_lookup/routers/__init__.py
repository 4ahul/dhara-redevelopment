"""
MCGM Property Lookup — FastAPI Router
Endpoints:
  POST /lookup        — async (background job), returns job_id immediately
  POST /lookup/sync   — waits for result, returns full data
  GET  /status/{id}  — poll job status
  GET  /health
"""

import base64
import contextlib
import logging
import os
import tempfile
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from ..core import settings
from ..schemas import (
    NearbyProperty,
    PropertyLookupRequest,
    PropertyLookupResponse,
    PropertyLookupStatus,
)
from ..services import ArcGISClient, MCGMBrowserScraper
from ..services.dp_gis_metrics import compute_all_gis_metrics
from ..services.geometry import (
    polygon_area_sqm,
    polygon_centroid_mercator,
    rings_to_wgs84,
    web_mercator_to_wgs84,
)
from ..services.storage import AsyncStorageService as StorageService
from ..services.visualization import generate_plot_map

logger = logging.getLogger(__name__)

router = APIRouter()


def get_storage() -> StorageService | None:
    try:
        return StorageService(settings.DATABASE_URL)
    except Exception as e:
        logger.warning("Storage unavailable: %s", e)
        return None


# ── Core lookup helper ────────────────────────────────────────────────────────


async def _do_lookup(
    lookup_id: str | None,
    ward: str,
    village: str,
    cts_no: str,
    tps_name: str | None = None,
    use_fp: bool = False,
    include_nearby: bool = True,
    storage: StorageService | None = None,
) -> dict:
    """Full lookup flow. Persists to DB if storage is available.

    Strategy:
      1. Try ArcGISClient.query_by_cts() — direct REST API (~2 s)
      2. If None → fall back to MCGMBrowserScraper (~30–60 s)
      3. Parse geometry, convert to WGS84, compute centroid + area
      4. If include_nearby: call ArcGISClient.query_nearby()
      5. Save to DB if storage available, always return result
    """
    feature: dict | None = None
    screenshot_b64: str | None = None
    _storage = storage  # May be None if DB unavailable

    # ── Step 1: Direct REST API ───────────────────────────────────────────
    try:
        async with httpx.AsyncClient() as http:
            client = ArcGISClient()
            feature = await client.query_by_cts(ward, village, cts_no, http)
    except Exception as e:
        logger.warning("Direct ArcGIS query failed: %s", e)

    building_data = {}
    screenshot_b64 = None

    # ── Step 2: Only run browser scraper if API failed ────────────────────────
    if feature is None:
        logger.info("API returned no result, falling back to browser scraper...")
        errors_to_log = []

        # Build village name variants to try (max 3 attempts)
        v_upper = village.upper().strip()
        village_variants = [v_upper, v_upper + " (W)", v_upper.replace(" ", "")]

        for attempt in range(3):
            village_attempt = (
                village_variants[attempt] if attempt < len(village_variants) else v_upper
            )
            try:
                scraper = MCGMBrowserScraper(headless=True)
                result = await scraper.scrape(
                    ward, village_attempt, cts_no, tps_name=tps_name, use_fp=use_fp
                )

                # Get building data from scraper
                scraped_building = result.get("building_data", {})
                if scraped_building:
                    building_data = scraped_building
                    logger.info("Got building data from scraper")

                feature = result.get("feature")
                screenshot_b64 = result.get("screenshot_b64")

                err_msg = result.get("error")

                if feature:
                    logger.info("Browser scraper succeeded on attempt %d", attempt + 1)
                    break

                if err_msg:
                    errors_to_log.append(f"Attempt {attempt + 1}: {err_msg}")

                if err_msg and ("not found" in err_msg.lower() or "invalid" in err_msg.lower()):
                    logger.info("Not retrying - property not in MCGM database")
                    break

                logger.info("Browser scraper attempt %d failed: %s", attempt + 1, err_msg)

            except Exception as e:
                err_str = str(e)
                errors_to_log.append(f"Attempt {attempt + 1}: {err_str}")
                logger.warning("Browser scraper exception on attempt %d: %s", attempt + 1, err_str)
    else:
        logger.info("API returned result, skipping browser scraper")

    if feature is None and not building_data:
        err = "; ".join(errors_to_log) if errors_to_log else "Browser scraper failed all attempts"
        if _storage and lookup_id:
            try:
                await storage.update_lookup(
                    lookup_id=lookup_id,
                    status="failed",
                    error_message=err,
                )
            except Exception as e:
                logger.warning("Failed to update lookup: %s", e)
        logger.error("Browser scraper failed: %s", err)
        return {"status": "failed", "error": err}

    if feature is None:
        err = "Property not found"
        if _storage and lookup_id:
            try:
                await storage.update_lookup(lookup_id=lookup_id, status="failed", error_message=err)
            except Exception as e:
                logger.warning("Failed to update lookup: %s", e)
        return {"status": "failed", "error": err}

    # ── Step 3: Parse geometry ────────────────────────────────────────────
    attrs = feature.get("attributes", {})
    geometry = feature.get("geometry", {})
    rings = geometry.get("rings", [])

    geometry_wgs84: list | None = None
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    area_sqm_val: float | None = None

    if rings:
        # Check if coordinates are in WGS84 (small numbers) or Web Mercator (large numbers)
        sample_x = rings[0][0][0] if rings and rings[0] else 0
        is_wgs84 = abs(sample_x) < 360  # WGS84 coords are -180..180

        if is_wgs84:
            # Already WGS84 — use directly
            geometry_wgs84 = rings
            # Centroid from averaging ring vertices
            flat = rings[0]
            centroid_lng = round(sum(p[0] for p in flat) / len(flat), 7)
            centroid_lat = round(sum(p[1] for p in flat) / len(flat), 7)
        else:
            # Web Mercator — convert
            geometry_wgs84 = rings_to_wgs84(rings)
            cx, cy = polygon_centroid_mercator(rings)
            centroid_lat, centroid_lng = web_mercator_to_wgs84(cx, cy)
            centroid_lat = round(centroid_lat, 7)
            centroid_lng = round(centroid_lng, 7)

        # Area: prefer SHAPE.AREA from attributes, fall back to polygon calculation
        shape_area = attrs.get("SHAPE.AREA")
        if shape_area:
            area_sqm_val = round(float(shape_area), 2)
        elif not is_wgs84:
            area_sqm_val = round(polygon_area_sqm(rings), 2)
        else:
            # Rough WGS84 area (not accurate but better than nothing)
            area_sqm_val = round(polygon_area_sqm(rings), 2) if rings else None

    tps_name = attrs.get("TPS_NAME")
    fp_no = attrs.get("FP_NO") or attrs.get("CTS_CS_NO")
    result_ward = attrs.get("WARD", ward)

    # ── Step 3.5: GIS Metrics & Map Generation ────────────────────────────
    gis_metrics = {}
    if rings:
        try:
            gis_metrics = await compute_all_gis_metrics(rings)
            # Generate high-fidelity map
            with tempfile.TemporaryDirectory() as tmpdir:
                filepath = generate_plot_map(
                    rings=rings,
                    output_dir=tmpdir,
                    setback_polys=gis_metrics.get("setback_polys"),
                    max_road_polys=gis_metrics.get("max_road_polys"),
                    abutting_lines=gis_metrics.get("abutting_lines"),
                    setback_area_m2=gis_metrics.get("setback_area_m2"),
                    max_road_width_m=gis_metrics.get("max_road_width_m"),
                    abutting_length_m=gis_metrics.get("abutting_length_m"),
                    roads_touching=gis_metrics.get("roads_touching"),
                    carriageway_entrances=gis_metrics.get("carriageway_entrances"),
                )
                if filepath and os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        map_bytes = f.read()
                        screenshot_b64 = base64.b64encode(map_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("GIS metrics / Map generation failed: %s", e)

    # ── Step 4: Nearby properties ─────────────────────────────────────────
    nearby: list[NearbyProperty] = []
    if include_nearby and rings:
        try:
            async with httpx.AsyncClient() as http:
                client = ArcGISClient()
                raw_nearby = await client.query_nearby(geometry, http)
            for nf in raw_nearby:
                na = nf.get("attributes", {})
                nb_fp = na.get("FP_NO", "")
                # Exclude the property itself
                if nb_fp and nb_fp != fp_no:
                    nearby.append(
                        NearbyProperty(
                            cts_no=nb_fp,
                            tps_name=na.get("TPS_NAME"),
                            ward=na.get("WARD"),
                        )
                    )
            logger.info("Found %d nearby properties", len(nearby))
        except Exception as e:
            logger.warning("Nearby query failed: %s", e)

    # ── Step 5: Persist ───────────────────────────────────────────────────
    screenshot_bytes: bytes | None = None
    if screenshot_b64:
        with contextlib.suppress(Exception):
            screenshot_bytes = base64.b64decode(screenshot_b64)

    nearby_dicts = [n.model_dump() for n in nearby] if nearby else []

    if _storage and lookup_id:
        try:
            await storage.update_lookup(
                lookup_id=lookup_id,
                status="completed",
                tps_name=tps_name,
                fp_no=fp_no,
                centroid_lat=centroid_lat,
                centroid_lng=centroid_lng,
                area_sqm=area_sqm_val,
                geometry_wgs84=geometry_wgs84,
                nearby_properties=nearby_dicts,
                map_screenshot=screenshot_bytes,
                raw_data=feature,
            )
        except Exception as e:
            logger.warning("Failed to persist lookup: %s", e)

    return {
        "status": "completed",
        "ward": result_ward,
        "village": village,
        "cts_no": cts_no,
        "tps_name": tps_name,
        "fp_no": fp_no,
        "geometry_wgs84": geometry_wgs84,
        "centroid_lat": centroid_lat,
        "centroid_lng": centroid_lng,
        "area_sqm": area_sqm_val,
        "nearby_properties": nearby_dicts,
        "building_data": building_data,
        "setback_area_m2": gis_metrics.get("setback_area_m2"),
        "max_road_width_m": gis_metrics.get("max_road_width_m"),
        "abutting_length_m": gis_metrics.get("abutting_length_m"),
        "reservation_area_m2": gis_metrics.get("reservation_area_m2"),
        "nalla_present": gis_metrics.get("nalla_present"),
        "industrial_present": gis_metrics.get("industrial_present"),
        "zone_code": gis_metrics.get("zone_code"),
        "roads_touching": gis_metrics.get("roads_touching"),
        "carriageway_entrances": gis_metrics.get("carriageway_entrances"),
    }


# ── Async endpoint ────────────────────────────────────────────────────────────


@router.post("/lookup", response_model=PropertyLookupResponse)
async def lookup_property(req: PropertyLookupRequest, background_tasks: BackgroundTasks, request: Request):
    """Submit a property lookup (processed in background). Poll GET /status/{id}."""
    storage = get_storage()
    ward_str = req.ward.value

    if storage:
        # 1. Check completed (30-day TTL)
        existing = await storage.find_completed_lookup(
            ward=ward_str, village=req.village, cts_no=req.cts_no
        )
        if existing:
            logger.info("Found completed lookup within 30 days. Returning existing ID: %s", existing["id"])
            return PropertyLookupResponse(
                id=str(existing["id"]),
                status=PropertyLookupStatus.COMPLETED,
                ward=req.ward,
                village=req.village,
                cts_no=req.cts_no,
                created_at=existing["created_at"],
            )

        # 2. Check processing
        processing = await storage.find_processing_lookup(
            ward=ward_str, village=req.village, cts_no=req.cts_no
        )
        if processing:
            logger.info("Found in-flight lookup. Returning existing ID: %s", processing["id"])
            return PropertyLookupResponse(
                id=str(processing["id"]),
                status=PropertyLookupStatus.PROCESSING,
                ward=req.ward,
                village=req.village,
                cts_no=req.cts_no,
                created_at=processing["created_at"],
            )

    # 3. Start new
    lookup_id = await storage.create_lookup(
        ward=ward_str,
        village=req.village,
        cts_no=req.cts_no,
    )

    background_tasks.add_task(
        _do_lookup,
        lookup_id,
        ward_str,
        req.village,
        req.cts_no,
        req.tps_name,
        req.use_fp,
        req.include_nearby,
        storage,
    )

    row = await storage.get_lookup(lookup_id)
    created_at = row["created_at"] if row else datetime.utcnow()

    return PropertyLookupResponse(
        id=lookup_id,
        status=PropertyLookupStatus.PROCESSING,
        ward=req.ward,
        village=req.village,
        cts_no=req.cts_no,
        created_at=created_at,
    )


# ── Status endpoint ───────────────────────────────────────────────────────────


@router.get("/status/{lookup_id}", response_model=PropertyLookupResponse)
async def get_lookup_status(lookup_id: str, request: Request):
    """Poll status of an async property lookup."""
    storage = get_storage()
    row = await storage.get_lookup(lookup_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lookup not found")

    nearby = None
    if row.get("nearby_properties"):
        np_data = row["nearby_properties"]
        if isinstance(np_data, str):
            import json as _json

            np_data = _json.loads(np_data)
        nearby = [NearbyProperty(**n) for n in np_data]

    download_url = f"{str(request.base_url).rstrip('/')}/download/{lookup_id}/screenshot"

    return PropertyLookupResponse(
        id=str(row["id"]),
        status=PropertyLookupStatus(row["status"]),
        ward=row.get("ward"),
        village=row.get("village"),
        cts_no=row.get("cts_no"),
        tps_name=row.get("tps_name"),
        fp_no=row.get("fp_no"),
        geometry_wgs84=row.get("geometry_wgs84"),
        centroid_lat=row.get("centroid_lat"),
        centroid_lng=row.get("centroid_lng"),
        area_sqm=row.get("area_sqm"),
        nearby_properties=nearby,
        download_url=download_url,
        error_message=row.get("error_message"),
        created_at=row.get("created_at"),
    )


# ── Download ─────────────────────────────────────────────────────────────────


@router.get("/download/{lookup_id}/screenshot")
async def download_screenshot(lookup_id: str, storage: StorageService = Depends(get_storage)):
    screenshot = await storage.get_screenshot(lookup_id)
    if not screenshot:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return Response(
        content=screenshot,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{lookup_id}_screenshot.png"'},
    )


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mcgm_property_lookup",
        "arcgis_layer_cached": ArcGISClient._layer_url is not None,
    }
