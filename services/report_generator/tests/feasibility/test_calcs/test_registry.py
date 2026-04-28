import pytest

from services.report_generator.feasibility.calc_registry import _clear_for_tests, get, register


def setup_function():
    _clear_for_tests()


def test_register_and_get():
    @register("my_calc")
    def my_calc(ctx, **kw):
        return 42

    assert get("my_calc") is my_calc
    assert my_calc(ctx={}) == 42


def test_duplicate_registration_raises():
    @register("dup")
    def a(ctx, **kw):
        return 1

    with pytest.raises(ValueError, match="Duplicate calc"):

        @register("dup")
        def b(ctx, **kw):
            return 2


def test_unknown_calc_raises():
    with pytest.raises(KeyError, match="Unknown calc"):
        get("nope")
