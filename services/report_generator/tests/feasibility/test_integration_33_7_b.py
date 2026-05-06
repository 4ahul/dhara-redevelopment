import importlib as _importlib
import json
from pathlib import Path

import openpyxl

from services.report_generator.feasibility.dispatcher import generate

_importlib.import_module("services.report_generator.feasibility.calcs")

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
MAPPING = Path(__file__).parents[2] / "mappings" / "33_7_B.yaml"
TEMPLATE = Path(__file__).parents[2] / "templates" / "FINAL TEMPLATE _ 33 (7)(B) .xlsx"


def test_golden_33_7_b(tmp_path):
    request = json.loads((FIXTURES / "golden_33_7_b_request.json").read_text())
    expected = json.loads((FIXTURES / "golden_33_7_b_cells.json").read_text())

    out = tmp_path / "out.xlsx"
    resp = generate(
        request=request,
        mapping_path=str(MAPPING),
        template_path=str(TEMPLATE),
        output_path=str(out),
    )

    assert resp.calculation_errors == []

    wb = openpyxl.load_workbook(out, data_only=False)
    mismatches = []
    for item in expected:
        sheet, coord = item["cell"].split("!", 1)
        actual = wb[sheet][coord].value
        exp = item["expected"]
        if (
            "tolerance" in item
            and isinstance(actual, (int, float))
            and isinstance(exp, (int, float))
        ):
            if abs(float(actual) - float(exp)) > item["tolerance"]:
                mismatches.append(f"{item['cell']}: expected {exp}, got {actual}")
        elif actual != exp:
            mismatches.append(f"{item['cell']}: expected {exp!r}, got {actual!r}")

    assert not mismatches, "Golden mismatches:\n" + "\n".join(mismatches[:10])
