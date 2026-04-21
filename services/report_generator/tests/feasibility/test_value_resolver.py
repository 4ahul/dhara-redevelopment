from feasibility.value_resolver import lookup


def test_nested_dict():
    data = {"mcgm_property": {"area_sqm": 1234.5}}
    assert lookup(data, "mcgm_property.area_sqm") == 1234.5


def test_top_level():
    assert lookup({"num_flats": 24}, "num_flats") == 24


def test_missing_returns_none():
    assert lookup({"a": {}}, "a.b.c") is None


def test_index_access():
    data = {"dp": {"nocs": ["hw", "rw"]}}
    assert lookup(data, "dp.nocs[0]") == "hw"
    assert lookup(data, "dp.nocs[5]") is None


def test_none_path_component():
    assert lookup({"a": None}, "a.b") is None
