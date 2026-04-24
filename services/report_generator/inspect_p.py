import openpyxl
wb = openpyxl.load_workbook("templates/FINAL TEMPLATE _ 33 (7)(B) .xlsx", data_only=False)
ws = wb["Details"]
for i in range(4, 12):
    cell = ws[f"P{i}"]
    color = cell.fill.fgColor.rgb if (cell.fill and cell.fill.fgColor) else "None"
    print(f"P{i} | Value: {cell.value} | Color: {color}")
