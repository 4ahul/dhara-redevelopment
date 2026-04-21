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
