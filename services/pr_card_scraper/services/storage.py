"""
PostgreSQL storage service for PR Cards.
Includes form_state persistence so CAPTCHA retry works across process restarts.
"""

import json
import logging
import uuid
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class StorageService:
    """PostgreSQL storage for PR Card records."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._init_db()

    # ------------------------------------------------------------------ #
    # Connection                                                           #
    # ------------------------------------------------------------------ #

    def _get_connection(self):
        return psycopg2.connect(self.database_url)

    # ------------------------------------------------------------------ #
    # Schema                                                               #
    # ------------------------------------------------------------------ #

    def _init_db(self):
        """Create table and indexes if they don't exist. Adds form_state column if missing."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS pr_cards (
                    id           UUID PRIMARY KEY,
                    district     TEXT NOT NULL,
                    taluka       TEXT NOT NULL,
                    village      TEXT NOT NULL,
                    survey_no    TEXT NOT NULL,
                    survey_no_part1 TEXT,
                    mobile       TEXT NOT NULL,
                    property_uid TEXT,
                    image        BYTEA,
                    captcha_image BYTEA,
                    status       VARCHAR(20) DEFAULT 'processing',
                    error_message TEXT,
                    form_state   JSONB,
                    image_url    TEXT,
                    extracted_data JSONB,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migrate: add columns if this is an existing table
            cur.execute("""
                ALTER TABLE pr_cards ADD COLUMN IF NOT EXISTS form_state JSONB;
            """)
            cur.execute("""
                ALTER TABLE pr_cards ADD COLUMN IF NOT EXISTS image_url TEXT;
            """)
            cur.execute("""
                ALTER TABLE pr_cards ADD COLUMN IF NOT EXISTS extracted_data JSONB;
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pr_cards_lookup
                ON pr_cards (survey_no, district, taluka, village);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pr_cards_created
                ON pr_cards (created_at DESC);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pr_cards_status
                ON pr_cards (status);
            """)

            conn.commit()
            cur.close()
            conn.close()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

    # ------------------------------------------------------------------ #
    # Write                                                                #
    # ------------------------------------------------------------------ #

    def create_pr_card(
        self,
        district: str,
        taluka: str,
        village: str,
        survey_no: str,
        survey_no_part1: Optional[str],
        mobile: str,
        property_uid: Optional[str],
        property_uid_known: bool = False,
        record_of_right: str = "Property Card",
        language: str = "EN",
    ) -> str:
        """Insert a new PR Card row and return its UUID."""
        pr_id = str(uuid.uuid4())
        form_state = {
            "district": district,
            "taluka": taluka,
            "village": village,
            "survey_no": survey_no,
            "survey_no_part1": survey_no_part1,
            "mobile": mobile,
            "property_uid": property_uid,
            "property_uid_known": property_uid_known,
            "record_of_right": record_of_right,
            "language": language,
        }

        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pr_cards
                    (id, district, taluka, village, survey_no, survey_no_part1,
                     mobile, property_uid, status, form_state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processing', %s)
                """,
                (
                    pr_id,
                    district,
                    taluka,
                    village,
                    survey_no,
                    survey_no_part1,
                    mobile,
                    property_uid,
                    json.dumps(form_state),
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Created PR Card: {pr_id}")
            return pr_id
        except Exception as e:
            logger.error(f"Failed to create PR Card: {e}")
            raise

    def update_pr_card(
        self,
        pr_id: str,
        status: str,
        image: Optional[bytes] = None,
        error_message: Optional[str] = None,
        captcha_image: Optional[bytes] = None,
        image_url: Optional[str] = None,
        extracted_data: Optional[dict] = None,
    ):
        """Update status, image, error, and/or image_url for an existing PR Card."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            if image:
                cur.execute(
                    """
                    UPDATE pr_cards
                    SET status = %s, image = %s, image_url = %s, 
                        extracted_data = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        status,
                        psycopg2.Binary(image),
                        image_url,
                        json.dumps(extracted_data) if extracted_data else None,
                        pr_id,
                    ),
                )
            elif captcha_image:
                cur.execute(
                    """
                    UPDATE pr_cards
                    SET status = %s, captcha_image = %s,
                        error_message = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (status, psycopg2.Binary(captcha_image), error_message, pr_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE pr_cards
                    SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (status, error_message, pr_id),
                )

            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Updated PR Card {pr_id}: status={status}")
        except Exception as e:
            logger.error(f"Failed to update PR Card: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    def get_pr_card(self, pr_id: str) -> Optional[dict]:
        """Fetch metadata (no binary blobs) for a PR Card."""
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, district, taluka, village, survey_no, survey_no_part1,
                       mobile, property_uid, status, error_message, form_state,
                       image_url, extracted_data, created_at
                FROM pr_cards
                WHERE id = %s
                """,
                (pr_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get PR Card: {e}")
            return None

    def get_form_state(self, pr_id: str) -> Optional[dict]:
        """Return the saved form_state JSON for a PR Card (used for captcha retry)."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT form_state FROM pr_cards WHERE id = %s", (pr_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row[0]:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get form_state: {e}")
            return None

    def get_pr_card_image(self, pr_id: str) -> Optional[bytes]:
        """Return the stored PR Card image bytes."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT image FROM pr_cards WHERE id = %s", (pr_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return bytes(row[0]) if row and row[0] else None
        except Exception as e:
            logger.error(f"Failed to get PR Card image: {e}")
            return None

    def get_captcha_image(self, pr_id: str) -> Optional[bytes]:
        """Return the stored CAPTCHA image bytes."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT captcha_image FROM pr_cards WHERE id = %s", (pr_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return bytes(row[0]) if row and row[0] else None
        except Exception as e:
            logger.error(f"Failed to get CAPTCHA image: {e}")
            return None

    def list_pr_cards(self, limit: int = 50, offset: int = 0) -> list:
        """Return a paginated list of PR Card metadata rows."""
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, district, taluka, village, survey_no, survey_no_part1,
                       mobile, status, created_at
                FROM pr_cards
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to list PR Cards: {e}")
            return []


import asyncio as _asyncio
import functools as _functools


class AsyncStorageService(StorageService):
    """
    Async-safe wrapper around StorageService.
    Offloads every psycopg2 call to a thread pool so the event loop is never blocked.
    """

    async def create_pr_card(self, **kwargs) -> str:
        return await _asyncio.to_thread(
            _functools.partial(StorageService.create_pr_card, self, **kwargs)
        )

    async def update_pr_card(self, **kwargs) -> None:
        return await _asyncio.to_thread(
            _functools.partial(StorageService.update_pr_card, self, **kwargs)
        )

    async def get_pr_card(self, pr_id: str):
        return await _asyncio.to_thread(StorageService.get_pr_card, self, pr_id)

    async def get_pr_card_image(self, pr_id: str):
        return await _asyncio.to_thread(StorageService.get_pr_card_image, self, pr_id)
