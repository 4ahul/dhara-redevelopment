import openpyxl
import sys

try:
    wb = openpyxl.load_workbook(r'C:\Users\Admin\Documents\Projects\redevelopment-ai\services\orchestrator\generated_reports\feasibility_fdddc573-46a2-4a5e-8ba9-310f084762ad.xlsx')
    
    print("=== Details Sheet ===")
    ws = wb['Details']
    cells_to_check = ['P4', 'M1', 'M2', 'P7', 'N17', 'R17', 'B19', 'N20', 'P49', 'N49', 
                      'O50', 'Q50', 'O51', 'Q51', 'O54', 'Q54', 'R25', 'R26', 'R27', 
                      'R28', 'R29', 'R30', 'R31', 'R32', 'R33', 'O40', 'J45', 'J54', 'J55']
    
    for cell in cells_to_check:
        val = ws[cell].value
        print(f"{cell}: {val}")
    
    print("\n=== Construction Cost Sheet ===")
    ws2 = wb['Construction Cost']
    print("D8:", ws2['D8'].value)
    print("D12:", ws2['D12'].value)
    print("D15:", ws2['D15'].value)
    print("H21:", ws2['H21'].value)
    
    print("\n=== SUMMARY 1 Sheet ===")
    ws3 = wb['SUMMARY 1']
    print("I98:", ws3['I98'].value)
    
    print("\n=== Profit & Loss Sheet ===")
    ws4 = wb['Profit & Loss Statement']
    cells_pnl = ['C19', 'D19', 'C20', 'D20', 'C21', 'D21', 'C22', 'D22', 'D28', 'C30', 'D30']
    for cell in cells_pnl:
        print(f"{cell}: {ws4[cell].value}")
        
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
