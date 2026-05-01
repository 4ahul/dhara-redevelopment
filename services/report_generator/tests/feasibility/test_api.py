from fastapi.testclient import TestClient
from main import app


def test_generate_feasibility_report_returns_xlsx(monkeypatch):
    client = TestClient(app)
    body = {
        "scheme": "33(7)(B)",
        "society_name": "Test CHS",
        "plot_area_sqm": 1500,
        "road_width_m": 18.3,
        "dp_report": {"road_width_m": 18.3, "required_nocs": ["Highway"]},
        "manual_inputs": {},
    }
    r = client.post("/generate/feasibility-report", json=body)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert int(r.headers.get("X-Report-Missing-Fields", "0")) >= 0
    assert int(r.headers.get("X-Report-Calc-Errors", "0")) == 0
    assert len(r.content) > 1000


def test_dossier_endpoint():
    client = TestClient(app)
    r = client.get("/feasibility/dossier?scheme=33(7)(B)")
    assert r.status_code == 200
    data = r.json()
    assert data["scheme"] == "33(7)(B)"
    assert isinstance(data["cells"], list)
    assert len(data["cells"]) > 0
