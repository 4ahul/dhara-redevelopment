import pytest
from feasibility.calcs import area_derivations  # registers
from feasibility.calc_registry import get
from feasibility.exceptions import MissingData


def test_sqft_from_sqm():
    fn = get("sqft_from_sqm")
    ctx = {"request": {"dp_report": {"area_sqm": 100}}, "resolved": {}}
    assert abs(fn(ctx, source_path="dp_report.area_sqm") - 1076.39) < 0.1


def test_sqft_from_sqm_missing_raises():
    fn = get("sqft_from_sqm")
    with pytest.raises(MissingData):
        fn({"request": {}, "resolved": {}}, source_path="dp_report.area_sqm")


def test_existing_bua_from_carpet_and_multiplier():
    fn = get("bua_from_carpet")
    ctx = {
        "request": {},
        "resolved": {
            "existing_residential_carpet_sqft": 10000,
            "residential_extra_multiplier": 1.3,
        },
    }
    assert fn(ctx, carpet="existing_residential_carpet_sqft", multiplier="residential_extra_multiplier") == 13000.0


def test_road_width_conditional_setback():
    fn = get("road_width_conditional_setback")
    ctx = {
        "request": {"dp_report": {"road_width_m": 10}},
        "resolved": {"setback_base_sqm": 500},
    }
    assert fn(ctx, min_width=9, max_width=12, proxy_name="setback_base_sqm") == 500
    ctx2 = {"request": {"dp_report": {"road_width_m": 20}}, "resolved": {"setback_base_sqm": 500}}
    assert fn(ctx2, min_width=9, max_width=12, proxy_name="setback_base_sqm") == 0
