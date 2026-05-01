import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    BASE_DIR: Path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    OUTPUT_DIR: Path = Path(os.getenv("REPORT_OUTPUT_DIR", "/tmp/reports"))
    TEMPLATES_DIR: Path = BASE_DIR / "templates"

    # App Settings
    # App
    APP_NAME: str = "report_generator"
    APP_VERSION: str = "1.0.0"
    # ── Financial / FSI Constants (Default to Mumbai Standard) ──────────────────
    ZONAL_FSI: float = float(os.getenv("ZONAL_FSI", 1.33))
    CONST_RATE_PER_SQFT: float = float(os.getenv("CONST_RATE_PER_SQFT", 4000.0))
    PROF_FEE_PER_SQFT: float = float(os.getenv("PROF_FEE_PER_SQFT", 125.0))
    CORPUS_PER_SQFT: float = float(os.getenv("CORPUS_PER_SQFT", 1250.0))
    TEMP_RESI_Y1_SQFT: float = float(os.getenv("TEMP_RESI_Y1_SQFT", 1800.0))
    TEMP_COMM_Y1_SQFT: float = float(os.getenv("TEMP_COMM_Y1_SQFT", 300.0))

    SALE_RATE_FALLBACK: float = float(os.getenv("SALE_RATE_FALLBACK", 65000.0))
    RR_OPEN_LAND_FALLBACK: float = float(os.getenv("RR_OPEN_LAND_FALLBACK", 200000.0))

    # ── Flat scheme key → template (kept for backward compatibility) ──
    # Internal lookup key is "{scheme}|{CLUBBING|INSITU}"
    # Standalone schemes (33(19), 33(9), 33(12)(B)_ONLY) have no INSITU variant
    SCHEME_TEMPLATE_MAP: dict[str, str] = {
        # ── CLUBBING variants ─────────────────────────────────────────
        "30(A)": "New base Feasibility as per Reg. 30(A), 33(7)(B) and 33 (20)(B)  - CLUBBING.xlsx",
        "33(7)(B)": "FINAL TEMPLATE _ 33 (7)(B).xlsx",
        "33(20)(B)": "New Base Feasiblity as per Reg. 33(20)(B) - CLUBBING.xlsx",
        "33(7)(A)": "New Base Feasiblity as per Reg. 30(A), 33(7)(A), 33(12)B and 33 (20)(B) - CLUBBING.xlsx",
        "33(12)(B)": "New Base Feasibility as per Reg. 30(A), 33(7)(B), 33(12)B and 33 (20)(B) - CLUBBING.xlsx",
        "33(12)(B)_ONLY": "New Base Feasiblity as per Reg. 30(A), 33(7)(B), 33(12)B.xlsx",
        # ── INSITU variants ───────────────────────────────────────────
        "30(A)_INSITU": "New Base Feasiblity as per Reg. 30(A), 33(7)(B) and 33 (20)(B) - INSITU.xlsx",
        "33(7)(B)_INSITU": "New Base Feasiblity as per Reg. 30(A), 33(7)(B) and 33 (20)(B) - INSITU.xlsx",
        "33(20)(B)_INSITU": "New Base Feasiblity as per Reg. 33(20)(B) - INSITU.xlsx",
        # ── Standalone schemes ────────────────────────────────────────
        "33(19)": "New Base 33 (19) 100% Feasibility Format.xlsx",
        "33(9)": "New Base Feasiblity as per Reg. 33 (9) - ONLY RESIDENTIAL.xlsx",
    }

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = True
        extra = "ignore"


def resolve_scheme_key(scheme: str, redevelopment_type: str = "CLUBBING") -> str:
    """Resolve the template key from scheme and type."""
    if not scheme:
        return ""

    # Normalize scheme naming for template map
    key = scheme.upper().replace("REG.", "").replace("REG", "").strip()

    # Handle INSITU variants if they exist in the map
    if redevelopment_type.upper() == "INSITU":
        insitu_key = f"{key}_INSITU"
        if insitu_key in settings.SCHEME_TEMPLATE_MAP:
            return insitu_key

    return key


settings = Settings()

# Export variables for legacy compatibility
BASE_DIR = settings.BASE_DIR
OUTPUT_DIR = settings.OUTPUT_DIR
TEMPLATES_DIR = settings.TEMPLATES_DIR
APP_NAME = settings.APP_NAME
APP_VERSION = settings.APP_VERSION

# Ensure output dir exists
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
