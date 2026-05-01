"""Playwright automation for CCAvenue UPI payment flow."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# ── Selectors — verify against live CCAvenue page if they break ───────────────
_SELECTORS = {
    # Bank selection modal (on MCGM page, before CCAvenue popup)
    "indian_bank": [
        "text=Indian Bank",
        "[id*='indianbank']",
        "img[alt*='Indian Bank']",
        "a:has-text('Indian Bank')",
    ],
    # CCAvenue UPI tab
    "upi_tab": [
        "li[id*='UPI']",
        "a[id*='upi']",
        "text=UPI",
        "[data-payment-option='UPI']",
    ],
    # UPI VPA input
    "vpa_input": [
        "input[id*='vpa']",
        "input[placeholder*='UPI ID']",
        "input[placeholder*='VPA']",
        "input[name='vpa']",
        "input[id*='upiId']",
    ],
    # Submit / Pay Now button on CCAvenue
    "submit_btn": [
        "button:has-text('Pay Now')",
        "input[value='Pay Now']",
        "button:has-text('Submit')",
        "button[id*='submit']",
    ],
    # Failure indicator
    "failure": [
        "text=Payment Failed",
        "text=Transaction Failed",
        "text=Failure",
        "[class*='error-msg']",
    ],
}


@dataclass
class PaymentResult:
    success: bool
    transaction_id: str | None = None
    error: str | None = None
    timed_out: bool = False


class CCAvenuePayer:
    """
    Handles the MCGM bank-selection modal and CCAvenue UPI payment popup.

    Usage:
        payer = CCAvenuePayer()
        result = await payer.pay(mcgm_page, upi_vpa="rahulsagar280103@okaxis")
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        poll_interval: float = 5.0,
    ):
        self._timeout = timeout_seconds
        self._poll = poll_interval

    async def pay(self, bank_selection_page: Page, upi_vpa: str) -> PaymentResult:
        """
        Receives the bank selection popup page (Indian Bank / Maharashtra Bank / Citi Bank).
          1. Click "Indian Bank" to open CCAvenue
          2. Select UPI tab, enter VPA, submit
          3. Poll until success redirect or timeout
        """
        logger.info(
            "CCAvenuePayer.pay() called — bank_selection_page URL: %s  title: %s",
            bank_selection_page.url,
            await bank_selection_page.title(),
        )
        # Wait for the page to fully render before searching
        try:
            await bank_selection_page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        try:
            ccavenue_page = await self._open_ccavenue(bank_selection_page)
            if ccavenue_page is None:
                return PaymentResult(success=False, error="CCAvenue page did not open")

            submitted = await self._submit_upi(ccavenue_page, upi_vpa)
            if not submitted:
                return PaymentResult(success=False, error="Failed to submit UPI VPA on CCAvenue")

            return await self._poll_for_result(ccavenue_page)

        except Exception as e:
            logger.error("CCAvenuePayer error: %s", e)
            return PaymentResult(success=False, error=str(e))

    async def _open_ccavenue(self, bank_page: Page) -> Page | None:
        """
        On the bank selection popup, find and click 'Indian Bank' to open CCAvenue.
        Handles both popup (window.open) and same-tab navigation.
        """
        # Log visible body for debugging
        try:
            body_text = await bank_page.evaluate(
                "() => document.body ? document.body.innerText.substring(0, 800) : 'no body'"
            )
            logger.info("Bank selection page text: %s", body_text)
        except Exception:
            pass

        # Find the Indian Bank element
        indian_bank_el = None
        for sel in _SELECTORS["indian_bank"]:
            try:
                el = bank_page.locator(sel).first
                if await el.is_visible(timeout=3_000):
                    indian_bank_el = el
                    logger.info("Found Indian Bank button via selector: %s", sel)
                    break
            except Exception:
                continue

        if indian_bank_el is None:
            # Log all links/buttons visible for diagnosis
            try:
                links = await bank_page.evaluate("""
                    () => Array.from(document.querySelectorAll('a,button,input[type=submit],input[type=button],img'))
                        .map(e => e.tagName + '#' + (e.id||'') + ' text=' + (e.innerText||e.alt||e.value||'').substring(0,40))
                        .join(' | ')
                """)
                logger.error(
                    "Indian Bank NOT found. URL=%s  Clickable elements: %s",
                    bank_page.url, links[:1000]
                )
            except Exception:
                logger.error("Indian Bank NOT found. URL=%s", bank_page.url)
            return None

        # Attempt 1: CCAvenue opens as new popup window
        try:
            async with bank_page.expect_popup(timeout=8_000) as popup_info:
                await indian_bank_el.click()
                logger.info("Clicked Indian Bank — waiting for CCAvenue popup")
            ccavenue_page = await popup_info.value()
            await ccavenue_page.wait_for_load_state("networkidle", timeout=20_000)
            logger.info("CCAvenue popup opened: %s", ccavenue_page.url)
            return ccavenue_page
        except Exception:
            pass

        # Attempt 2: Check if bank_page already navigated to CCAvenue
        await asyncio.sleep(1)
        if "ccavenue" in bank_page.url.lower():
            logger.info("CCAvenue opened same-tab: %s", bank_page.url)
            try:
                await bank_page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass
            return bank_page

        # Attempt 3: Try clicking again with same-tab navigation wait
        try:
            async with bank_page.expect_navigation(timeout=15_000):
                await indian_bank_el.click()
                logger.info("Clicked Indian Bank (attempt 3) — waiting for navigation")
            await bank_page.wait_for_load_state("networkidle", timeout=20_000)
            logger.info("Navigated to: %s", bank_page.url)
            return bank_page
        except Exception as e:
            logger.error("Indian Bank click failed all attempts: %s", e)
            return None

    async def _submit_upi(self, page: Page, vpa: str) -> bool:
        """Select UPI tab, enter VPA, click Pay Now."""
        logger.info("_submit_upi on page: %s", page.url)
        try:
            # Click UPI tab
            for sel in _SELECTORS["upi_tab"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3_000):
                        await el.click()
                        logger.info("Selected UPI tab")
                        await page.wait_for_timeout(1_000)
                        break
                except Exception:
                    continue

            # Fill VPA
            for sel in _SELECTORS["vpa_input"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3_000):
                        await el.fill(vpa)
                        logger.info("Entered UPI VPA: %s", vpa)
                        break
                except Exception:
                    continue

            # Click Pay Now
            for sel in _SELECTORS["submit_btn"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3_000):
                        await el.click()
                        logger.info("Clicked Pay Now — waiting for UPI collect request")
                        return True
                except Exception:
                    continue

            # No Pay Now button found — abort UPI submission
            logger.error("Could not find Pay Now button — aborting UPI submission")
            return False

        except Exception as e:
            logger.error("UPI submit error: %s", e)
            return False

    async def _poll_for_result(self, page: Page) -> PaymentResult:
        """Poll CCAvenue page URL every poll_interval seconds for up to timeout_seconds."""
        elapsed = 0.0
        while elapsed < self._timeout:
            url = page.url

            if "orderStatus=Success" in url or "status=Success" in url.lower():
                txn_id = _extract_order_no(url)
                logger.info("CCAvenue payment SUCCESS — txn_id=%s", txn_id)
                return PaymentResult(success=True, transaction_id=txn_id)

            if "orderStatus=Failure" in url or "orderStatus=Aborted" in url:
                logger.warning("CCAvenue payment FAILED — url=%s", url)
                return PaymentResult(success=False, error="Payment failed or aborted by user")

            # Also check for failure elements on the page
            for sel in _SELECTORS["failure"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=500):
                        return PaymentResult(success=False, error="CCAvenue showed failure message")
                except Exception:
                    pass

            await asyncio.sleep(self._poll)
            elapsed += self._poll

        logger.warning("CCAvenue payment timed out after %ss", self._timeout)
        return PaymentResult(
            success=False,
            timed_out=True,
            error=f"No UPI approval received within {self._timeout}s",
        )


def _extract_order_no(url: str) -> str | None:
    """Extract orderNo param from CCAvenue success URL."""
    try:
        params = parse_qs(urlparse(url).query)
        return (params.get("orderNo") or params.get("order_id") or [None])[0]
    except Exception:
        return None
