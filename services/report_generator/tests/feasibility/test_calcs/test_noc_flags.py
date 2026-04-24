from feasibility.calcs import noc_flags  # registers
from feasibility.calc_registry import get


def test_noc_required():
    fn = get("noc_flag_from_dp")
    ctx = {"request": {"dp_report": {"required_nocs": ["Highway", "Railway"]}}, "resolved": {}}
    assert fn(ctx, noc_type="highway") == 1
    assert fn(ctx, noc_type="railway") == 1
    assert fn(ctx, noc_type="asi") == 0


def test_noc_missing_field_returns_zero():
    fn = get("noc_flag_from_dp")
    ctx = {"request": {}, "resolved": {}}
    assert fn(ctx, noc_type="highway") == 0

