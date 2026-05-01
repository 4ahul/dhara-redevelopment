import openpyxl
wb = openpyxl.load_workbook("templates/FINAL TEMPLATE _ 33 (7)(B) .xlsx", data_only=False)
ws = wb["Details"]
for col in ["O", "Q"]:
    for row in range(44, 48):
        print(f"{col}{row}: '{ws[f'{col}{row}'].value}'")
