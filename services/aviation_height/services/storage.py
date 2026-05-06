import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, db_path: str = "services/aviation_height/db/aviation_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS height_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    site_elevation REAL,
                    max_height_m REAL,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_coords ON height_cache (lat, lng)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init aviation DB: {e}")

    def get_cached_height(self, lat: float, lng: float, tolerance: float = 0.0001) -> dict | None:
        """Find cached result within tolerance (approx 10m) and 30-day TTL."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT data_json FROM height_cache 
                WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
                  AND created_at > datetime('now', '-30 days')
                ORDER BY created_at DESC LIMIT 1
            """, (lat - tolerance, lat + tolerance, lng - tolerance, lng + tolerance))
            row = cur.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Failed to query aviation cache: {e}")
            return None

    def cache_height(self, lat: float, lng: float, site_elevation: float, max_height_m: float, data: dict):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO height_cache (lat, lng, site_elevation, max_height_m, data_json)
                VALUES (?, ?, ?, ?, ?)
            """, (lat, lng, site_elevation, max_height_m, json.dumps(data)))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to cache aviation result: {e}")

storage_service = StorageService()
