import openpyxl
from openpyxl.styles import PatternFill
from feasibility.inspector import enumerate_fillable_cells


def _make_wb(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Details"
    yellow = PatternFill("solid", fgColor="FFFFFF00")
    black = PatternFill("solid", fgColor="FF000000")
    ws["A1"].value = "label"
    ws["B1"].value = "Input"
    ws["B1"].fill = yellow
    ws["C1"].value = "Output"
    ws["C1"].fill = black
    ws["D1"].value = "=B1+1"
    path = tmp_path / "t.xlsx"
    wb.save(path)
    return path


def test_enumerate_yellow_and_black_only(tmp_path):
    path = _make_wb(tmp_path)
    wb = openpyxl.load_workbook(path, data_only=False)
    cells = enumerate_fillable_cells(wb)
    coords = {(c["sheet"], c["coord"], c["kind"]) for c in cells}
    assert ("Details", "B1", "yellow") in coords
    assert ("Details", "C1", "black") in coords
    assert not any(c["coord"] == "A1" for c in cells)
    assert not any(c["coord"] == "D1" for c in cells)
