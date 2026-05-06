"""
DP Report Service — PostgreSQL Storage
"""

import asyncio as _asyncio
import contextlib
import functools as _functools
import json
import logging
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class StorageService:
    """PostgreSQL storage for DP Report records."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._init_db()

    def _get_connection(self):
        return psycopg2.connect(self.database_url)

    def _init_db(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dp_reports (
                    id              UUID PRIMARY KEY,
                    ward            TEXT NOT NULL,
                    village         TEXT NOT NULL,
                    cts_no          TEXT NOT NULL,
                    lat             DOUBLE PRECISION,
                    lng             DOUBLE PRECISION,
                    zone_code       TEXT,
                    zone_name       TEXT,
                    road_width_m    DOUBLE PRECISION,
                    fsi             DOUBLE PRECISION,
                    height_limit_m  DOUBLE PRECISION,
                    reservations    JSONB,
                    crz_zone        BOOLEAN,
                    heritage_zone   BOOLEAN,
                    dp_remarks      TEXT,
                    raw_attributes  JSONB,
                    map_screenshot  BYTEA,
                    status          VARCHAR(20) DEFAULT 'processing',
                    error_message   TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    -- DP Remark PDF parsed fields
                    report_type             VARCHAR(20),
                    reference_no            VARCHAR(100),
                    report_date             VARCHAR(20),
                    applicant_name          VARCHAR(200),
                    cts_nos                 JSONB,
                    fp_no                   VARCHAR(50),
                    tps_name                VARCHAR(200),
                    reservations_affecting  VARCHAR(500),
                    reservations_abutting   VARCHAR(500),
                    designations_affecting  VARCHAR(500),
                    designations_abutting   VARCHAR(500),
                    dp_roads                VARCHAR(500),
                    proposed_road           VARCHAR(200),
                    proposed_road_widening  VARCHAR(200),
                    rl_remarks_traffic      TEXT,
                    rl_remarks_survey       TEXT,
                    water_pipeline          JSONB,
                    sewer_line              JSONB,
                    drainage                JSONB,
                    ground_level            JSONB,
                    heritage_building       VARCHAR(10),
                    heritage_precinct       VARCHAR(10),
                    heritage_buffer_zone    VARCHAR(10),
                    archaeological_site     VARCHAR(10),
                    archaeological_buffer   VARCHAR(10),
                    existing_amenities_affecting VARCHAR(500),
                    existing_amenities_abutting  VARCHAR(500),
                    crz_zone_details        TEXT,
                    high_voltage_line       TEXT,
                    buffer_sgnp             TEXT,
                    flamingo_esz            TEXT,
                    corrections_dcpr        TEXT,
                    modifications_sec37     TEXT,
                    road_realignment        TEXT,
                    ep_nos                  JSONB,
                    sm_nos                  JSONB,
                    pdf_text                TEXT,
                    pdf_bytes               BYTEA,
                    -- Payment tracking
                    payment_status          VARCHAR(20),
                    payment_transaction_id  VARCHAR(100),
                    payment_amount          NUMERIC(10,2),
                    payment_paid_at         TIMESTAMPTZ
                );
            """)
            # Add columns to existing tables (idempotent)
            new_columns = [
                ("report_type", "VARCHAR(20)"),
                ("reference_no", "VARCHAR(100)"),
                ("report_date", "VARCHAR(20)"),
                ("applicant_name", "VARCHAR(200)"),
                ("cts_nos", "JSONB"),
                ("fp_no", "VARCHAR(50)"),
                ("tps_name", "VARCHAR(200)"),
                ("reservations_affecting", "VARCHAR(500)"),
                ("reservations_abutting", "VARCHAR(500)"),
                ("designations_affecting", "VARCHAR(500)"),
                ("designations_abutting", "VARCHAR(500)"),
                ("dp_roads", "VARCHAR(500)"),
                ("proposed_road", "VARCHAR(200)"),
                ("proposed_road_widening", "VARCHAR(200)"),
                ("rl_remarks_traffic", "TEXT"),
                ("rl_remarks_survey", "TEXT"),
                ("water_pipeline", "JSONB"),
                ("sewer_line", "JSONB"),
                ("drainage", "JSONB"),
                ("ground_level", "JSONB"),
                ("heritage_building", "VARCHAR(10)"),
                ("heritage_precinct", "VARCHAR(10)"),
                ("heritage_buffer_zone", "VARCHAR(10)"),
                ("archaeological_site", "VARCHAR(10)"),
                ("archaeological_buffer", "VARCHAR(10)"),
                ("existing_amenities_affecting", "VARCHAR(500)"),
                ("existing_amenities_abutting", "VARCHAR(500)"),
                ("crz_zone_details", "TEXT"),
                ("high_voltage_line", "TEXT"),
                ("buffer_sgnp", "TEXT"),
                ("flamingo_esz", "TEXT"),
                ("corrections_dcpr", "TEXT"),
                ("modifications_sec37", "TEXT"),
                ("road_realignment", "TEXT"),
                ("ep_nos", "JSONB"),
                ("sm_nos", "JSONB"),
                ("pdf_text", "TEXT"),
                ("pdf_bytes", "BYTEA"),
                ("payment_status", "VARCHAR(20)"),
                ("payment_transaction_id", "VARCHAR(100)"),
                ("payment_amount", "NUMERIC(10,2)"),
                ("payment_paid_at", "TIMESTAMPTZ"),
            ]
            for col_name, col_type in new_columns:
                with contextlib.suppress(Exception):
                    cur.execute(
                        f"ALTER TABLE dp_reports ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    )
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_dp_reports_lookup
                ON dp_reports (ward, village, cts_no);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_dp_reports_status
                ON dp_reports (status);
            """)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("dp_reports table ready")
        except Exception as e:
            logger.exception("DB init error: %s", e)

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_report(
        self,
        ward: str,
        village: str,
        cts_no: str,
        lat: float | None = None,
        lng: float | None = None,
    ) -> str:
        report_id = str(uuid.uuid4())
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO dp_reports (id, ward, village, cts_no, lat, lng, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'processing')
                """,
                (report_id, ward, village, cts_no, lat, lng),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Created DP report: %s", report_id)
            return report_id
        except Exception as e:
            logger.exception("Failed to create DP report: %s", e)
            raise

    # Fields that need JSON serialization
    _JSON_FIELDS = {
        "reservations",
        "raw_attributes",
        "cts_nos",
        "water_pipeline",
        "sewer_line",
        "drainage",
        "ground_level",
        "ep_nos",
        "sm_nos",
    }
    # Fields that need binary wrapping
    _BINARY_FIELDS = {"map_screenshot", "pdf_bytes"}
    # All valid column names for dynamic update
    _ALL_FIELDS = {
        "zone_code",
        "zone_name",
        "road_width_m",
        "fsi",
        "height_limit_m",
        "crz_zone",
        "heritage_zone",
        "dp_remarks",
        "error_message",
        "report_type",
        "reference_no",
        "report_date",
        "applicant_name",
        "fp_no",
        "tps_name",
        "reservations_affecting",
        "reservations_abutting",
        "designations_affecting",
        "designations_abutting",
        "dp_roads",
        "proposed_road",
        "proposed_road_widening",
        "rl_remarks_traffic",
        "rl_remarks_survey",
        "heritage_building",
        "heritage_precinct",
        "heritage_buffer_zone",
        "archaeological_site",
        "archaeological_buffer",
        "existing_amenities_affecting",
        "existing_amenities_abutting",
        "crz_zone_details",
        "high_voltage_line",
        "buffer_sgnp",
        "flamingo_esz",
        "corrections_dcpr",
        "modifications_sec37",
        "road_realignment",
        "pdf_text",
        "payment_status",
        "payment_transaction_id",
        "payment_amount",
        "payment_paid_at",
    }

    def update_report(self, report_id: str, status: str, **kwargs):
        """Update a DP report with any combination of fields."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            set_parts = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
            values = [status]

            for key, val in kwargs.items():
                if key in self._JSON_FIELDS:
                    set_parts.append(f"{key} = %s")
                    values.append(json.dumps(val) if val is not None else None)
                elif key in self._BINARY_FIELDS:
                    set_parts.append(f"{key} = %s")
                    values.append(psycopg2.Binary(val) if val else None)
                elif key in self._ALL_FIELDS:
                    set_parts.append(f"{key} = %s")
                    values.append(val)

            values.append(report_id)
            sql = f"UPDATE dp_reports SET {', '.join(set_parts)} WHERE id = %s"
            cur.execute(sql, values)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Updated DP report %s: status=%s", report_id, status)
        except Exception as e:
            logger.exception("Failed to update DP report %s: %s", report_id, e)
            raise

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_report(self, report_id: str) -> dict | None:
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM dp_reports WHERE id = %s", (report_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.exception("Failed to get DP report %s: %s", report_id, e)
            return None

    def get_screenshot(self, report_id: str) -> bytes | None:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT map_screenshot FROM dp_reports WHERE id = %s", (report_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row[0]:
                return bytes(row[0])
            return None
        except Exception as e:
            logger.exception("Failed to get screenshot for %s: %s", report_id, e)
            return None

    def find_completed_report(self, ward: str, village: str, cts_no: str) -> dict | None:
        """Find the most recent completed DP report for these parameters within 30 days."""
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            w = ward.strip().upper()
            v = village.strip().upper()
            c = cts_no.strip()

            cur.execute(
                """
                SELECT * FROM dp_reports
                WHERE ward = %s AND village = %s AND cts_no = %s 
                  AND status = 'completed'
                  AND created_at > NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (w, v, c),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.exception("Failed to find completed report: %s", e)
            return None

    def find_processing_report(self, ward: str, village: str, cts_no: str) -> dict | None:
        """Find an in-flight processing job (started in the last 10 mins)."""
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            w = ward.strip().upper()
            v = village.strip().upper()
            c = cts_no.strip()

            cur.execute(
                """
                SELECT id, status, created_at FROM dp_reports
                WHERE ward = %s AND village = %s AND cts_no = %s 
                  AND status = 'processing'
                  AND created_at > NOW() - INTERVAL '10 minutes'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (w, v, c),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.exception("Failed to find processing report: %s", e)
            return None


class AsyncStorageService(StorageService):
    """Async-safe wrapper — offloads psycopg2 calls to thread pool."""

    async def create_report(self, **kwargs) -> str:
        return await _asyncio.to_thread(
            _functools.partial(StorageService.create_report, self, **kwargs)
        )

    async def update_report(self, **kwargs) -> None:
        return await _asyncio.to_thread(
            _functools.partial(StorageService.update_report, self, **kwargs)
        )

    async def get_report(self, report_id: str):
        return await _asyncio.to_thread(StorageService.get_report, self, report_id)

    async def get_screenshot(self, report_id: str):
        return await _asyncio.to_thread(StorageService.get_screenshot, self, report_id)

    async def find_completed_report(self, **kwargs):
        return await _asyncio.to_thread(
            _functools.partial(StorageService.find_completed_report, self, **kwargs)
        )

    async def find_processing_report(self, **kwargs):
        return await _asyncio.to_thread(
            _functools.partial(StorageService.find_processing_report, self, **kwargs)
        )
