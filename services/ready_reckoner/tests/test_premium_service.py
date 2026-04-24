import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sys
import os
from pathlib import Path

# Setup path for imports
root_path = Path(__file__).parent.parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

# Test data for PremiumRequest
SAMPLE_PREMIUM_REQUEST = {
    "district": "Mumbai City",
    "taluka": "Byculla",
    "locality": "Prabhadevi",
    "zone": "G/S",
    "sub_zone": "",
    "property_type": "residential",
    "property_area_sqm": 100.0,
    "amenities_premium_percentage": 10.0,
    "depreciation_percentage": 5.0,
    "permissible_bua_sqft": 1000.0,
    "residential_bua_sqft": 800.0,
    "commercial_bua_sqft": 200.0,
    "scheme": "33(7)(B)",
    "fungible_residential_sqft": 100.0,
    "fungible_commercial_sqft": 50.0,
    "staircase_area_sqft": 20.0,
    "general_tdr_area_sqft": 50.0,
    "slum_tdr_area_sqft": 30.0,
    "staircase_ratio": 0.10,
    "fungible_res_ratio": 0.25,
    "fungible_comm_ratio": 0.30,
    "premium_fsi_ratio": 0.40,
    "scrutiny_fee_sqft": 2.0,
    "plot_area_sqm": 150.0,
    "dev_charge_sqm": 500.0,
    "luc_charge_sqm": 100.0,
}

@pytest.mark.unit
class TestPremiumService:
    """Test suite for PremiumService"""

    @patch('services.ready_reckoner.services.premium_service.rr_repository')
    def test_calculate_premiums_basic(self, mock_rr_repo):
        """Test basic premium calculation with mocked repository"""
        from services.ready_reckoner.services.premium_service import PremiumService, premium_service
        
        # Mock the repository response
        mock_record = {
            "location": {
                "district": "Mumbai City",
                "taluka": "Byculla", 
                "locality": "Prabhadevi",
                "village": "",
                "zone": "G/S",
                "sub_zone": ""
            },
            "administrative": {
                "type_of_area": "Residential",
                "local_body_name": "MCGM",
                "local_body_type": "Municipal Corporation"
            },
            "applicability": {
                "commence_from": "01/04/2023",
                "commence_to": "31/03/2024",
                "landmark_note": ""
            },
            "rates": [
                {"category": "Land", "value": "50000", "previous_year_rate": "45000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "11.11"},
                {"category": "Residential", "value": "60000", "previous_year_rate": "55000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "9.09"},
                {"category": "Shop", "value": "90000", "previous_year_rate": "80000", 
                 "increase_amount": "10000", "increase_or_decrease_percent": "12.5"}
            ]
        }
        mock_rr_repo.get_rates.return_value = mock_record
        
        # Create service instance and test
        svc = PremiumService()
        from services.ready_reckoner.schemas import PremiumRequest
        
        req = PremiumRequest(**SAMPLE_PREMIUM_REQUEST)
        result = svc.calculate_premiums(req)
        
        # Assertions
        assert result.total_property_value > 0
        assert result.grand_total > 0
        assert result.total_fsi_tdr_premiums >= 0
        assert result.total_mcgm_charges >= 0
        assert len(result.line_items) > 0
        
        # Check that we have the expected sections in line items
        line_item_descriptions = [item.description for item in result.line_items]
        assert "Property Base Value" in line_item_descriptions
        assert "Total Property Value (Ready Reckoner)" in line_item_descriptions
        assert "Additional FSI Premium" in line_item_descriptions
        assert "Development Charges (MCGM)" in line_item_descriptions

    @patch('services.ready_reckoner.services.premium_service.rr_repository')
    def test_calculate_premiums_open_land(self, mock_rr_repo):
        """Test premium calculation for open land property type"""
        from services.ready_reckoner.services.premium_service import PremiumService
        
        # Mock the repository response
        mock_record = {
            "location": {
                "district": "Mumbai City",
                "taluka": "Byculla", 
                "locality": "Prabhadevi",
                "village": "",
                "zone": "G/S",
                "sub_zone": ""
            },
            "administrative": {
                "type_of_area": "Residential",
                "local_body_name": "MCGM",
                "local_body_type": "Municipal Corporation"
            },
            "applicability": {
                "commence_from": "01/04/2023",
                "commence_to": "31/03/2024",
                "landmark_note": ""
            },
            "rates": [
                {"category": "Land", "value": "50000", "previous_year_rate": "45000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "11.11"},
                {"category": "Residential", "value": "60000", "previous_year_rate": "55000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "9.09"},
                {"category": "Shop", "value": "90000", "previous_year_rate": "80000", 
                 "increase_amount": "10000", "increase_or_decrease_percent": "12.5"}
            ]
        }
        mock_rr_repo.get_rates.return_value = mock_record
        
        # Create service instance and test
        svc = PremiumService()
        from services.ready_reckoner.schemas import PremiumRequest
        
        # Modify request for open land
        open_land_request = SAMPLE_PREMIUM_REQUEST.copy()
        open_land_request["property_type"] = "open_land"
        open_land_request["property_area_sqm"] = 200.0
        
        req = PremiumRequest(**open_land_request)
        result = svc.calculate_premiums(req)
        
        # Assertions
        assert result.total_property_value > 0
        assert result.grand_total > 0
        
        # For open land, base RR rate should be the land rate
        line_item_descriptions = [item.description for item in result.line_items]
        base_value_items = [item for item in result.line_items if "Property Base Value" in item.description]
        assert len(base_value_items) > 0

    @patch('services.ready_reckoner.services.premium_service.rr_repository')
    def test_calculate_premiums_commercial(self, mock_rr_repo):
        """Test premium calculation for commercial property type"""
        from services.ready_reckoner.services.premium_service import PremiumService
        
        # Mock the repository response
        mock_record = {
            "location": {
                "district": "Mumbai City",
                "taluka": "Byculla", 
                "locality": "Prabhadevi",
                "village": "",
                "zone": "G/S",
                "sub_zone": ""
            },
            "administrative": {
                "type_of_area": "Commercial",
                "local_body_name": "MCGM",
                "local_body_type": "Municipal Corporation"
            },
            "applicability": {
                "commence_from": "01/04/2023",
                "commence_to": "31/03/2024",
                "landmark_note": ""
            },
            "rates": [
                {"category": "Land", "value": "50000", "previous_year_rate": "45000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "11.11"},
                {"category": "Residential", "value": "60000", "previous_year_rate": "55000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "9.09"},
                {"category": "Shop", "value": "90000", "previous_year_rate": "80000", 
                 "increase_amount": "10000", "increase_or_decrease_percent": "12.5"}
            ]
        }
        mock_rr_repo.get_rates.return_value = mock_record
        
        # Create service instance and test
        svc = PremiumService()
        from services.ready_reckoner.schemas import PremiumRequest
        
        # Modify request for commercial
        commercial_request = SAMPLE_PREMIUM_REQUEST.copy()
        commercial_request["property_type"] = "commercial"
        commercial_request["property_area_sqm"] = 150.0
        
        req = PremiumRequest(**commercial_request)
        result = svc.calculate_premiums(req)
        
        # Assertions
        assert result.total_property_value > 0
        assert result.grand_total > 0

    @patch('services.ready_reckoner.services.premium_service.rr_repository')
    def test_calculate_premiums_with_zero_values(self, mock_rr_repo):
        """Test premium calculation with zero values for optional fields"""
        from services.ready_reckoner.services.premium_service import PremiumService
        
        # Mock the repository response
        mock_record = {
            "location": {
                "district": "Mumbai City",
                "taluka": "Byculla", 
                "locality": "Prabhadevi",
                "village": "",
                "zone": "G/S",
                "sub_zone": ""
            },
            "administrative": {
                "type_of_area": "Residential",
                "local_body_name": "MCGM",
                "local_body_type": "Municipal Corporation"
            },
            "applicability": {
                "commence_from": "01/04/2023",
                "commence_to": "31/03/2024",
                "landmark_note": ""
            },
            "rates": [
                {"category": "Land", "value": "50000", "previous_year_rate": "45000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "11.11"},
                {"category": "Residential", "value": "60000", "previous_year_rate": "55000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "9.09"},
                {"category": "Shop", "value": "90000", "previous_year_rate": "80000", 
                 "increase_amount": "10000", "increase_or_decrease_percent": "12.5"}
            ]
        }
        mock_rr_repo.get_rates.return_value = mock_record
        
        # Create service instance and test
        svc = PremiumService()
        from services.ready_reckoner.schemas import PremiumRequest
        
        # Modify request with zero values for optional fields
        minimal_request = SAMPLE_PREMIUM_REQUEST.copy()
        minimal_request["permissible_bua_sqft"] = 0
        minimal_request["residential_bua_sqft"] = 0
        minimal_request["commercial_bua_sqft"] = 0
        minimal_request["fungible_residential_sqft"] = 0
        minimal_request["fungible_commercial_sqft"] = 0
        minimal_request["staircase_area_sqft"] = 0
        minimal_request["general_tdr_area_sqft"] = 0
        minimal_request["slum_tdr_area_sqft"] = 0
        minimal_request["plot_area_sqm"] = 0
        
        req = PremiumRequest(**minimal_request)
        result = svc.calculate_premiums(req)
        
        # Assertions
        assert result.total_property_value >= 0  # Could be zero if area is zero
        assert result.grand_total >= 0
        
        # Should still have property valuation line items even with zero values
        line_item_descriptions = [item.description for item in result.line_items]
        assert "Property Base Value" in line_item_descriptions

    def test_helper_functions(self):
        """Test helper functions in isolation"""
        from services.ready_reckoner.services.premium_service import (
            _extract_rates, _build_location, _build_administrative, 
            _build_applicability, _build_rr_rates
        )
        
        # Test _extract_rates
        record = {
            "rates": [
                {"category": "Land", "value": "50000"},
                {"category": "Residential", "value": "60000"},
                {"category": "Shop", "value": "90000"}
            ]
        }
        rates = _extract_rates(record)
        assert rates["land"] == 50000.0
        assert rates["residential"] == 60000.0
        assert rates["shop"] == 90000.0
        
        # Test _build_location
        location_record = {
            "location": {
                "district": "Test District",
                "taluka": "Test Taluka",
                "locality": "Test Locality",
                "village": "Test Village",
                "zone": "Test Zone",
                "sub_zone": "Test Sub Zone"
            }
        }
        from services.ready_reckoner.schemas import PremiumRequest
        req = PremiumRequest(
            district="Req District",
            taluka="Req Taluka", 
            locality="Req Locality",
            zone="Req Zone",
            sub_zone="Req Sub Zone",
            property_type="residential",
            property_area_sqm=100.0
        )
        location_info = _build_location(location_record, req)
        assert location_info.district == "Test District"
        assert location_info.taluka == "Test Taluka"
        assert location_info.locality == "Test Locality"
        assert location_info.village == "Test Village"
        assert location_info.zone == "Test Zone"
        assert location_info.sub_zone == "Test Sub Zone"
        
        # Test _build_administrative
        admin_record = {
            "administrative": {
                "type_of_area": "Residential",
                "local_body_name": "Test Body",
                "local_body_type": "Corporation"
            }
        }
        admin_info = _build_administrative(admin_record)
        assert admin_info.type_of_area == "Residential"
        assert admin_info.local_body_name == "Test Body"
        assert admin_info.local_body_type == "Corporation"
        
        # Test _build_applicability
        app_record = {
            "applicability": {
                "commence_from": "01/01/2023",
                "commence_to": "31/12/2023",
                "landmark_note": "Near station"
            }
        }
        app_info = _build_applicability(app_record)
        assert app_info.commence_from == "01/01/2023"
        assert app_info.commence_to == "31/12/2023"
        assert app_info.landmark_note == "Near station"
        
        # Test _build_rr_rates
        rates_record = {
            "rates": [
                {"category": "Land", "value": "50000", "previous_year_rate": "45000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "11.11"},
                {"category": "Residential", "value": "60000", "previous_year_rate": "55000", 
                 "increase_amount": "5000", "increase_or_decrease_percent": "9.09"}
            ]
        }
        rr_rates = _build_rr_rates(rates_record)
        assert len(rr_rates) == 2
        assert rr_rates[0].category == "Land"
        assert rr_rates[0].value == 50000.0
        assert rr_rates[0].previous_year_rate == 45000.0
        assert rr_rates[0].increase_amount == 5000.0
        assert rr_rates[0].increase_or_decrease_percent == 11.11

