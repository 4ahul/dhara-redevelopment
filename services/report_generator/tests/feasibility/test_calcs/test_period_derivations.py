import pytest
from feasibility.calcs import period_derivations  # registers
from feasibility.calc_registry import get
from feasibility.exceptions import MissingData


def test_completion_months_from_area_rate():
    fn = get("completion_months_from_area")
    ctx = {"request": {}, "resolved": {"bua_sqft": 120000}}
    assert fn(ctx, area_name="bua_sqft", rate_sqft_per_month=5000) == 24


def test_completion_months_minimum_floor():
    fn = get("completion_months_from_area")
    ctx = {"request": {}, "resolved": {"bua_sqft": 1000}}
    assert fn(ctx, area_name="bua_sqft", rate_sqft_per_month=5000, minimum=12) == 12


def test_completion_missing_raises():
    fn = get("completion_months_from_area")
    with pytest.raises(MissingData):
        fn({"request": {}, "resolved": {}}, area_name="bua_sqft", rate_sqft_per_month=5000)
