import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_orchestrator_app_imports_cleanly():
    from services.orchestrator.core.config import settings
    from services.orchestrator.main import app

    assert app.title == "Dhara AI"
    assert app.version == settings.APP_VERSION
    assert settings.APP_PORT == 8000


@pytest.mark.asyncio
async def test_run_agent_requires_real_location_inputs():
    from services.orchestrator.agent.runner import run_agent

    result = await run_agent({"society_name": "Unit Test Society"}, request_id="unit-test")

    assert result["status"] == "error"
    assert "site address" in result["error"]


def test_dependencies_do_not_export_removed_service_providers():
    from services.orchestrator.core import dependencies

    assert not hasattr(dependencies, "get_notification_service")
    assert not hasattr(dependencies, "get_settings_service")
