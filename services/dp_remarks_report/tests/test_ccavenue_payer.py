"""Tests for CCAvenuePayer."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest


def _make_ccavenue_page(url="https://secure.ccavenue.com/transaction/transaction.do"):
    """Build a minimal Playwright Page mock for the CCAvenue popup."""
    page = AsyncMock()
    type(page).url = PropertyMock(return_value=url)
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    locator = AsyncMock()
    locator.is_visible = AsyncMock(return_value=True)
    locator.click = AsyncMock()
    locator.fill = AsyncMock()
    locator.first = locator
    page.locator = MagicMock(return_value=locator)
    return page


def _make_mcgm_page(ccavenue_page):
    """Build a Playwright Page mock for the MCGM portal with popup support."""
    page = AsyncMock()
    locator = AsyncMock()
    locator.is_visible = AsyncMock(return_value=True)
    locator.click = AsyncMock()
    locator.first = locator
    page.locator = MagicMock(return_value=locator)

    popup_info = AsyncMock()
    popup_info.__aenter__ = AsyncMock(return_value=popup_info)
    popup_info.__aexit__ = AsyncMock(return_value=False)
    popup_info.value = AsyncMock(return_value=ccavenue_page)
    page.expect_popup = MagicMock(return_value=popup_info)
    return page


@pytest.mark.asyncio
async def test_pay_success():
    """pay() returns success=True when CCAvenue URL contains orderStatus=Success."""
    from services.dp_remarks_report.services.ccavenue_payer import CCAvenuePayer, PaymentResult

    ccavenue_page = _make_ccavenue_page(
        url="https://secure.ccavenue.com/?orderStatus=Success&orderNo=TXN123"
    )
    mcgm_page = _make_mcgm_page(ccavenue_page)

    payer = CCAvenuePayer(timeout_seconds=5, poll_interval=0.01)
    result = await payer.pay(mcgm_page, "test@okaxis")

    assert isinstance(result, PaymentResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_pay_timeout():
    """pay() returns timed_out=True when CCAvenue never redirects within timeout."""
    from services.dp_remarks_report.services.ccavenue_payer import _SELECTORS, CCAvenuePayer

    ccavenue_page = _make_ccavenue_page(
        url="https://secure.ccavenue.com/transaction/transaction.do"
    )
    mcgm_page = _make_mcgm_page(ccavenue_page)

    # Submit/UPI/VPA selectors must be visible so _submit_upi succeeds (returns True).
    # Failure selectors must stay invisible so polling reaches the timeout.
    failure_selectors = set(_SELECTORS["failure"])

    def _locator_factory(sel):
        locator = AsyncMock()
        locator.first = locator
        locator.click = AsyncMock()
        locator.fill = AsyncMock()
        # Invisible for failure selectors; visible for everything else
        locator.is_visible = AsyncMock(return_value=(sel not in failure_selectors))
        return locator

    ccavenue_page.locator = MagicMock(side_effect=_locator_factory)

    payer = CCAvenuePayer(timeout_seconds=0.05, poll_interval=0.01)
    result = await payer.pay(mcgm_page, "test@okaxis")

    assert result.success is False
    assert result.timed_out is True


@pytest.mark.asyncio
async def test_pay_returns_transaction_id():
    """pay() extracts orderNo from the success URL as transaction_id."""
    from services.dp_remarks_report.services.ccavenue_payer import CCAvenuePayer

    ccavenue_page = _make_ccavenue_page(
        url="https://secure.ccavenue.com/?orderStatus=Success&orderNo=CC20260427ABC"
    )
    mcgm_page = _make_mcgm_page(ccavenue_page)

    payer = CCAvenuePayer(timeout_seconds=5, poll_interval=0.01)
    result = await payer.pay(mcgm_page, "test@okaxis")

    assert result.transaction_id == "CC20260427ABC"


@pytest.mark.asyncio
async def test_pay_failure_url():
    """pay() returns success=False when CCAvenue URL contains orderStatus=Failure."""
    from services.dp_remarks_report.services.ccavenue_payer import CCAvenuePayer

    ccavenue_page = _make_ccavenue_page(url="https://secure.ccavenue.com/?orderStatus=Failure")
    mcgm_page = _make_mcgm_page(ccavenue_page)

    payer = CCAvenuePayer(timeout_seconds=5, poll_interval=0.01)
    result = await payer.pay(mcgm_page, "test@okaxis")

    assert result.success is False
    assert result.timed_out is False


def test_extract_order_no_from_url():
    """_extract_order_no parses orderNo from CCAvenue success URL."""
    from services.dp_remarks_report.services.ccavenue_payer import _extract_order_no

    url = "https://secure.ccavenue.com/?orderStatus=Success&orderNo=TXN_ABC123"
    assert _extract_order_no(url) == "TXN_ABC123"

    assert _extract_order_no("https://example.com/no-params") is None
