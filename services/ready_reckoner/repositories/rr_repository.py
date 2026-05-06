import asyncio
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_DATE_SUFFIX = re.compile(
    r"\s+\d+\s*(st|nd|rd|th)?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{4}.*",
    re.IGNORECASE,
)


def _norm(s) -> str:
    """Lowercase + strip whitespace."""
    return str(s).strip().lower() if s else ""


def _norm_village(s: str) -> str:
    """Strip date suffixes scraped into village names, e.g.
    'GIRGAON 1st April 2026 To 31st March 2027' → 'girgaon'."""
    return _DATE_SUFFIX.sub("", s).strip().lower()


class ReadyReckonerRepository:
    def __init__(self):
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "rr_rates_2026.jsonl",
        )
        self._records: list[dict] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    async def _load(self):
        if self._loaded:
            return

        loop = asyncio.get_event_loop()
        try:
            if not os.path.exists(self._db_path):
                logger.error("RR database not found at %s", self._db_path)
                return

            def read_file():
                recs = []
                with open(self._db_path, encoding="utf-8") as f:
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line:
                            recs.append(json.loads(stripped_line))
                return recs

            self._records = await loop.run_in_executor(None, read_file)
            self._loaded = True
            logger.info("Loaded %d RR rate records", len(self._records))
        except Exception as exc:
            logger.exception("Error loading RR rates: %s", exc)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def get_rates(
        self,
        district: str = "",
        taluka: str = "",
        locality: str = "",
        zone: str = "",
        sub_zone: str = "",
    ) -> dict:
        """Return the best-matching RR record for the given location identifiers."""
        await self._load()

        d = _norm(district)
        t = _norm(taluka)
        loc = _norm(locality)
        z = _norm(zone)
        sz = _norm(sub_zone)

        # Compound zone that the caller might mean, e.g. z="5" sz="5/43" → "5/43"
        caller_compound = f"{z}/{sz}" if sz and not z.endswith(f"/{sz}") else z

        best_score = 0
        best_record: dict = {}

        for record in self._records:
            rl = record.get("location", {})
            rd = _norm(rl.get("district", ""))
            rt = _norm(rl.get("taluka", ""))
            rloc = _norm(rl.get("locality", ""))
            rv = _norm_village(rl.get("village", ""))
            rz = _norm(rl.get("zone", ""))
            rsz = _norm(rl.get("sub_zone", ""))

            score = 0

            # --- administrative tier ---
            if d and rd == d:
                score += 8
            if t and rt == t:
                score += 4

            # --- locality tier ---
            if loc:
                if rloc == loc:
                    score += 8
                elif rv == loc:
                    score += 6

            # --- zone tier ---
            if z:
                if rz == z:
                    score += 4
                elif rz == caller_compound:
                    # record stores compound in zone field
                    score += 3
                elif rz.startswith(z + "/"):
                    score += 2

            # --- sub_zone tier ---
            if sz:
                if rsz == sz:
                    score += 4
                elif rz == caller_compound and not rsz:
                    # compound stored in zone field, no separate sub_zone
                    score += 3

            if score > best_score:
                best_score = score
                best_record = record

        if best_score == 0:
            logger.warning(
                "No RR match for district=%s taluka=%s locality=%s zone=%s sub_zone=%s",
                district,
                taluka,
                locality,
                zone,
                sub_zone,
            )
            return {}

        logger.debug(
            "Matched RR record (score=%d): locality=%s zone=%s",
            best_score,
            best_record.get("location", {}).get("locality"),
            best_record.get("location", {}).get("zone"),
        )
        return best_record


rr_repository = ReadyReckonerRepository()
