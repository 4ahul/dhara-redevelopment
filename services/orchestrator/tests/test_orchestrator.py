from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.orchestrator.core.config import settings
from services.orchestrator.main import app


def test_orchestrator_app_metadata():
    assert app.title == "Dhara AI"
    assert app.version == settings.APP_VERSION
