"""
MCGM Property Lookup — PostgreSQL Storage
Stores lookup results for async polling and caching.
"""

import json
import logging
import uuid
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class StorageService:
    """PostgreSQL storage for MCGM property lookup records."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        # Schema is managed by Alembic

    # ── Connection ────────────────────────────────────────────────────────────

    def _get_connection(self):
        return psycopg2.connect(self.database_url)

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self):
        """Create table and indexes if they don't exist."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS property_lookups (
                    id                  UUID PRIMARY KEY,
                    ward                TEXT NOT NULL,
                    village             TEXT NOT NULL,
                    cts_no              TEXT NOT NULL,
                    tps_name            TEXT,
                    fp_no               TEXT,
                    centroid_lat        DOUBLE PRECISION,
                    centroid_lng        DOUBLE PRECISION,
                    area_sqm            DOUBLE PRECISION,
                    geometry_wgs84      JSONB,
                    nearby_properties   JSONB,
                    map_screenshot      BYTEA,
                    raw_data            JSONB,
                    status              VARCHAR(20) DEFAULT 'processing',
                    error_message       TEXT,
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_property_lookups_lookup
                ON property_lookups (ward, village, cts_no);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_property_lookups_created
                ON property_lookups (created_at DESC);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_property_lookups_status
                ON property_lookups (status);
            """)

            conn.commit()
            cur.close()
            conn.close()
            logger.info("Database initialized (property_lookups table ready)")
        except Exception as e:
            logger.error("Database initialization error: %s", e)

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_lookup(self, ward: str, village: str, cts_no: str) -> str:
        """Insert a new lookup row in 'processing' state. Returns UUID."""
        lookup_id = str(uuid.uuid4())
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO property_lookups (id, ward, village, cts_no, status)
                VALUES (%s, %s, %s, %s, 'processing')
                """,
                (lookup_id, ward, village, cts_no),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Created lookup: %s (ward=%s village=%s cts=%s)", lookup_id, ward, village, cts_no)
            return lookup_id
        except Exception as e:
            logger.error("Failed to create lookup: %s", e)
            raise

    def update_lookup(
        self,
        lookup_id: str,
        status: str,
        tps_name: Optional[str] = None,
        fp_no: Optional[str] = None,
        centroid_lat: Optional[float] = None,
        centroid_lng: Optional[float] = None,
        area_sqm: Optional[float] = None,
        geometry_wgs84: Optional[list] = None,
        nearby_properties: Optional[list] = None,
        map_screenshot: Optional[bytes] = None,
        raw_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ):
        """Update a lookup record with results or error."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE property_lookups SET
                    status            = %s,
                    tps_name          = %s,
                    fp_no             = %s,
                    centroid_lat      = %s,
                    centroid_lng      = %s,
                    area_sqm          = %s,
                    geometry_wgs84    = %s,
                    nearby_properties = %s,
                    map_screenshot    = %s,
                    raw_data          = %s,
                    error_message     = %s,
                    updated_at        = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    status,
                    tps_name,
                    fp_no,
                    centroid_lat,
                    centroid_lng,
                    area_sqm,
                    json.dumps(geometry_wgs84) if geometry_wgs84 is not None else None,
                    json.dumps(nearby_properties) if nearby_properties is not None else None,
                    psycopg2.Binary(map_screenshot) if map_screenshot else None,
                    json.dumps(raw_data) if raw_data is not None else None,
                    error_message,
                    lookup_id,
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Updated lookup %s: status=%s", lookup_id, status)
        except Exception as e:
            logger.error("Failed to update lookup %s: %s", lookup_id, e)
            raise

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_lookup(self, lookup_id: str) -> Optional[dict]:
        """Fetch a lookup record (without binary map_screenshot blob)."""
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, ward, village, cts_no, tps_name, fp_no,
                       centroid_lat, centroid_lng, area_sqm,
                       geometry_wgs84, nearby_properties,
                       raw_data, status, error_message, created_at
                FROM property_lookups
                WHERE id = %s
                """,
                (lookup_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error("Failed to get lookup %s: %s", lookup_id, e)
            return None

    def get_screenshot(self, lookup_id: str) -> Optional[bytes]:
        """Return the map screenshot bytes for a completed lookup."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT map_screenshot FROM property_lookups WHERE id = %s",
                (lookup_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return bytes(row[0]) if row and row[0] else None
        except Exception as e:
            logger.error("Failed to get screenshot for %s: %s", lookup_id, e)
            return None


import asyncio as _asyncio
import functools as _functools


class AsyncStorageService(StorageService):
    """
    Async-safe wrapper around StorageService.
    Offloads every psycopg2 call to a thread pool so the event loop is never blocked.
    """

    async def create_lookup(self, ward: str, village: str, cts_no: str) -> str:
        return await _asyncio.to_thread(
            StorageService.create_lookup, self, ward, village, cts_no
        )

    async def update_lookup(self, **kwargs) -> None:
        return await _asyncio.to_thread(
            _functools.partial(StorageService.update_lookup, self, **kwargs)
        )

    async def get_lookup(self, lookup_id: str):
        return await _asyncio.to_thread(StorageService.get_lookup, self, lookup_id)

    async def get_screenshot(self, lookup_id: str):
        return await _asyncio.to_thread(StorageService.get_screenshot, self, lookup_id)

