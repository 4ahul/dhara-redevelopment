import sqlite3
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, db_path: str = "services/site_analysis/db/site_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_id TEXT NOT NULL,
                    query TEXT,
                    lat REAL,
                    lng REAL,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_place_id ON analysis_cache (place_id)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init site analysis DB: {e}")

    def get_cached_analysis(self, place_id: str) -> dict | None:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT data_json FROM analysis_cache 
                WHERE place_id = ? AND created_at > datetime('now', '-30 days')
                ORDER BY created_at DESC LIMIT 1
            """, (place_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Failed to query site analysis cache: {e}")
            return None

    def cache_analysis(self, place_id: str, query: str, lat: float, lng: float, data: dict):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO analysis_cache (place_id, query, lat, lng, data_json)
                VALUES (?, ?, ?, ?, ?)
            """, (place_id, query, lat, lng, json.dumps(data)))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to cache site analysis result: {e}")

storage_service = StorageService()
