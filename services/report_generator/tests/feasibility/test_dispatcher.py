from feasibility.dispatcher import apply_transform


def test_transform_float():
    assert apply_transform("3.14", "float") == 3.14


def test_transform_int():
    assert apply_transform("42", "int") == 42


def test_transform_str():
    assert apply_transform(42, "str") == "42"


def test_transform_bool_toggle():
    assert apply_transform(True, "bool_toggle") == 1
    assert apply_transform(False, "bool_toggle") == 0
    assert apply_transform("yes", "bool_toggle") == 1
    assert apply_transform("no", "bool_toggle") == 0


def test_transform_percent():
    assert apply_transform(50, "percent") == 0.5


def test_transform_none_passthrough():
    assert apply_transform(None, "float") is None


def test_transform_none_type_passthrough():
    assert apply_transform("abc", None) == "abc"


import pytest
from feasibility.mapping_loader import MappingEntry
from feasibility.exceptions import MissingData
from feasibility.dispatcher import resolve_entry
from feasibility.calc_registry import register, _clear_for_tests


def setup_function():
    _clear_for_tests()


def test_resolve_from_path():
    e = MappingEntry("Details!A1", "yellow", "a", from_="x.y", fallback=0)
    ctx = {"request": {"x": {"y": 7}}, "resolved": {}}
    assert resolve_entry(e, ctx) == 7


def test_resolve_sources_first_non_none():
    e = MappingEntry("Details!A1", "yellow", "a", sources=["x.y", "x.z"], fallback=0)
    ctx = {"request": {"x": {"z": 3}}, "resolved": {}}
    assert resolve_entry(e, ctx) == 3


def test_resolve_all_none_raises():
    e = MappingEntry("Details!A1", "yellow", "a", from_="nope", fallback=0)
    with pytest.raises(MissingData):
        resolve_entry(e, {"request": {}, "resolved": {}})


def test_resolve_const():
    e = MappingEntry("Details!A1", "yellow", "a", const=1.28, fallback=0)
    assert resolve_entry(e, {"request": {}, "resolved": {}}) == 1.28


def test_resolve_calc():
    @register("times2")
    def times2(ctx, x: float):
        return float(x) * 2
    e = MappingEntry("Details!A1", "black", "a", calc="times2", calc_args={"x": 5}, fallback=0)
    assert resolve_entry(e, {"request": {}, "resolved": {}}) == 10.0
