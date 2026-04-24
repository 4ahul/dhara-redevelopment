import pytest
from feasibility.calcs import financial_derivations  # registers
from feasibility.calc_registry import get
from feasibility.exceptions import MissingData


def test_bank_guarantee_15pct():
    fn = get("bank_guarantee_15pct")
    ctx = {"request": {}, "resolved": {"corpus_fund_commercial": 100000}}
    assert fn(ctx, based_on="corpus_fund_commercial") == 15000.0


def test_bank_guarantee_missing_raises():
    fn = get("bank_guarantee_15pct")
    with pytest.raises(MissingData):
        fn({"request": {}, "resolved": {}}, based_on="corpus_fund_commercial")


def test_percentage_of():
    fn = get("percentage_of")
    ctx = {"request": {}, "resolved": {"base": 200}}
    assert fn(ctx, based_on="base", pct=0.18) == 36.0


def test_sum_resolved():
    fn = get("sum_resolved")
    ctx = {"request": {}, "resolved": {"a": 1, "b": 2, "c": 3}}
    assert fn(ctx, names=["a", "b", "c"]) == 6
