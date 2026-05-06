"""Address Autocomplete -- ArcGIS Suggest (free, no API key)

GET /api/address/suggest?q=<text>   -- autocomplete suggestions (Mumbai only)
GET /api/address/geocode?q=<text>   -- resolve to lat/lng + structured address
"""

from fastapi import APIRouter, Query
from services.orchestrator.services.address_service import suggest_addresses, geocode_address

router = APIRouter(prefix="/address", tags=["Address Autocomplete"])


@router.get("/suggest")
async def suggest(
    q: str = Query(min_length=2, max_length=200),
    max: int = Query(8, ge=1, le=15, alias="maxSuggestions"),
    category: str = Query(None),
):
    """Autocomplete address suggestions for Mumbai. No auth required."""
    return {"suggestions": await suggest_addresses(q, max_suggestions=max, category=category)}


@router.get("/geocode")
async def geocode(
    q: str = Query(None, max_length=500),
    magicKey: str = Query(None),
):
    """Resolve suggestion to full address + lat/lng. Pass magicKey (preferred) or q."""
    result = await geocode_address(text=q, magic_key=magicKey)
    if not result:
        return {"data": None, "error": {"message": "Address not found"}}
    return {"data": result, "error": None}
