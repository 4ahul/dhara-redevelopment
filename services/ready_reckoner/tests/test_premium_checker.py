from utils import setup_path
setup_path("premium_checker")

from services.ready_reckoner.logic.premium_checker.schemas import PremiumRequest
from services.ready_reckoner.logic.premium_checker.services.premium_service import premium_service

SAMPLE_PREMIUM_REQUEST = {
    "ward": "G/S",
    "plot_area_sqm": 1372.56,
    "property_area_sqm": 1372.56,
    "property_type": "residential",
    "scheme": "33(7)(B)",
    "permissible_bua_sqft": 44322,
    "residential_bua_sqft": 44322,
}

def test_premium_checker_flow():
    print("Testing Premium Checker Service Flow...")
    req = PremiumRequest(**SAMPLE_PREMIUM_REQUEST)
    result = premium_service.calculate_premiums(req)
    
    print(f"- Grand Total: ₹{result.grand_total}")
    print(f"- Total in Crores: ₹{result.grand_total_crore} Cr")
    
    assert result.grand_total > 0

if __name__ == "__main__":
    test_premium_checker_flow()


