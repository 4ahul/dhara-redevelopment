import pytest

from services.report_generator.feasibility.calc_registry import get
from services.report_generator.feasibility.exceptions import MissingData


def test_floors_from_max_height_exact():
    fn = get("floors_from_max_height")
    ctx = {"request": {"height": {"max_height_m": 30}}, "resolved": {}}
    assert fn(ctx, floor_height_m=3) == 10


def test_floors_from_max_height_floor():
    fn = get("floors_from_max_height")
    ctx = {"request": {"height": {"max_height_m": 31.5}}, "resolved": {}}
    assert fn(ctx, floor_height_m=3) == 10


def test_podium_allowed_by_plot_area_thresholds():
    fn = get("podium_count_from_plot_area")
    assert fn({"request": {"plot_area_sqm": 800}, "resolved": {}}) == 0
    assert fn({"request": {"plot_area_sqm": 1500}, "resolved": {}}) == 1
    assert fn({"request": {"plot_area_sqm": 3000}, "resolved": {}}) == 2
    assert fn({"request": {"plot_area_sqm": 6000}, "resolved": {}}) == 3


def test_floors_missing_raises():
    fn = get("floors_from_max_height")
    with pytest.raises(MissingData):
        fn({"request": {}, "resolved": {}}, floor_height_m=3)
