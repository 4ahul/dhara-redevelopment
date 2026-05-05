import asyncio
import contextlib
import logging
import os
import time

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..captcha_solver import CaptchaSolver
from ..data_extractor import DataExtractor
from ..validator import ValidationError, validate_location
from .base import BaseBrowser
from .extractor import ImageExtractor
from .mahabhumi import MahabhumiFormHandler

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Exact Devanagari text of the "Go Forward / Continue" button on the disclaimer page
_CONTINUE_BTN_TEXT = "पुढे जा"


class MahabhumiScraper:
    """Orchestrates the scraping of Mahabhumi Bhulekh PR Cards."""

    def __init__(self, browser: BaseBrowser):
        self.browser = browser
        self.captcha_solver = CaptchaSolver()
        self.data_extractor = DataExtractor()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception, RuntimeError)),
    )
    async def scrape_pr_card(self, **kwargs) -> dict:
        """
        Full async scrape flow with production-grade retries.
        """
        captcha_override = kwargs.pop("captcha_override", None)
        on_captcha = kwargs.pop("on_captcha", None)
        kwargs.pop("property_uid", None)
        # Fixed values for this service
        kwargs["record_of_right"] = "Property Card"
        kwargs["language"] = "EN"

        # Validate District → Taluka → Village before launching browser
        try:
            validate_location(
                kwargs.get("district", ""),
                kwargs.get("taluka", ""),
                kwargs.get("village"),
            )
        except ValidationError as ve:
            return {"status": "failed", "error": str(ve)}

        page = await self.browser.new_page()

        # Track popup windows
        popup_page = None

        async def on_popup(p):
            nonlocal popup_page
            logger.info("Detected popup window")
            popup_page = p

        page.on("popup", on_popup)

        form_handler = MahabhumiFormHandler(page)
        extractor = ImageExtractor(page)

        try:
            # ── 1. Navigate ────────────────────────────────────────────────
            await form_handler.navigate_to_base()

            # ── 2. Fill Form ───────────────────────────────────────────────
            await form_handler.fill_form(**kwargs)

            # ── 3. Solve CAPTCHA ───────────────────────────────────────────
            # Activate interception BEFORE submitting so we catch the image response
            extractor.activate()

            if captcha_override:
                logger.info(f"Using manual CAPTCHA override: {captcha_override}")
                await form_handler.submit_form(captcha_override)
            else:
                captcha_result = await self._solve_captcha_loop(
                    form_handler, extractor, on_captcha, form_kwargs=kwargs
                )
                if captcha_result is not None:
                    # captcha_required or failure — return early
                    return captcha_result

            # ── 4. Wait for result page ────────────────────────────────────
            await asyncio.sleep(3)

            # Log state for diagnostics
            try:
                logger.info(f"Post-submit URL: {page.url}")
                logger.info(f"Post-submit title: {await page.title()}")
            except Exception:
                pass

            # ── 5. Handle popup vs inline result ──────────────────────────
            if popup_page:
                logger.info("Popup window detected — waiting for it to load")
                with contextlib.suppress(Exception):
                    await popup_page.wait_for_load_state("networkidle", timeout=20000)
                active_extractor = ImageExtractor(popup_page)
                active_extractor.activate()
            else:
                active_extractor = extractor
                # Try to click the "पुढे जा" (Continue) button to get to the
                # standalone image page where #ContentPlaceHolder1_ImgPC appears.
                await _click_continue_button(page)

                # After Continue, check for popup again
                await asyncio.sleep(5)
                if popup_page:
                    logger.info("Popup opened after Continue — switching to it")
                    with contextlib.suppress(Exception):
                        await popup_page.wait_for_load_state("networkidle", timeout=20000)
                    active_extractor = ImageExtractor(popup_page)
                    active_extractor.activate()

                # Also check for View links in a result grid
                if not popup_page:
                    await _click_view_link(page)
                    await asyncio.sleep(5)
                    if popup_page:
                        with contextlib.suppress(Exception):
                            await popup_page.wait_for_load_state("networkidle", timeout=20000)
                        active_extractor = ImageExtractor(popup_page)
                        active_extractor.activate()

            # ── 6. Extract Image URL and Navigate Directly ─────────────────
            # Primary: wait for #ContentPlaceHolder1_ImgPC (45s)
            _, image_url = await active_extractor.wait_for_pr_card_image(timeout=45)

            if not image_url or "base64" in image_url:
                logger.info("Primary URL extraction failed — trying get_best_image fallback")
                _, image_url = await active_extractor.get_best_image(timeout=20)

            if image_url and image_url.startswith("http"):
                logger.info(f"Navigating directly to public image URL: {image_url}")
                # Create a new page for the image to ensure session isolation
                img_page = await self.browser.new_page()
                try:
                    # Direct navigation to the image URL
                    img_resp = await img_page.goto(image_url, wait_until="load", timeout=30000)
                    if img_resp and img_resp.ok:
                        image_bytes = await img_resp.body()
                        logger.info(
                            f"Successfully downloaded image from direct URL ({len(image_bytes):,} bytes)"
                        )
                    else:
                        logger.warning("Direct navigation failed, falling back to capture")
                        image_bytes = None
                except Exception as e:
                    logger.warning(f"Error navigating to image URL: {e}")
                    image_bytes = None
                finally:
                    await img_page.close()
            else:
                image_bytes = None

            # ── 7. Save result ─────────────────────────────────────────────
            timestamp = int(time.time())
            ext = "jpg" if image_url and "jpeg" in (image_url or "") else "png"
            output_path = os.path.join(OUTPUT_DIR, f"pr_card_{timestamp}.{ext}")

            if not image_bytes:
                # Absolute last resort: screenshot
                logger.warning("No image extracted — saving screenshot as last resort")
                output_path = os.path.join(OUTPUT_DIR, f"pr_card_{timestamp}_screenshot.png")
                target_page = popup_page if popup_page else page
                await ImageExtractor(target_page).screenshot_fallback(output_path)
                return {
                    "status": "completed",
                    "image_bytes": None,
                    "output_path": output_path,
                    "image_url": None,
                    "error": "Image not found — saved screenshot as fallback",
                }

            with open(output_path, "wb") as f:
                f.write(image_bytes)
            logger.info(f"PR card image saved: {output_path} ({len(image_bytes):,} bytes)")

            extracted_data = await self.data_extractor.extract(image_bytes)

            return {
                "status": "completed",
                "image_bytes": image_bytes,
                "output_path": output_path,
                "image_url": image_url,
                "extracted_data": extracted_data,
            }

        except Exception as e:
            logger.error(f"Scraping failed: {e}", exc_info=True)
            try:
                ts = int(time.time())
                diag_path = os.path.join(OUTPUT_DIR, f"fail_diag_{ts}.png")
                await page.screenshot(path=diag_path, full_page=True)
                logger.info(f"Saved diagnostic screenshot: {diag_path}")
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}
        finally:
            if popup_page:
                with contextlib.suppress(Exception):
                    await popup_page.close()
            await page.close()

    async def _solve_captcha_loop(
        self,
        form_handler: MahabhumiFormHandler,
        extractor: ImageExtractor,
        on_captcha,
        form_kwargs: dict | None = None,
    ) -> dict | None:
        """
        Auto-solve CAPTCHA with 3-tier strategy:
          Tier 1: LLM Vision (Gemini Flash → GPT-4o) — ~90% first-try accuracy
          Tier 2: ddddocr OCR — offline fallback
          Tier 3: pytesseract — last resort

        Strategy: 1 best candidate per fresh image, 5 attempts total.
        After a failed submit, the ASP.NET postback may clear form fields,
        so we re-fill the form before each retry.
        Returns a result dict on failure/captcha_required, or None on success.
        """
        max_attempts = 5
        last_captcha_img = None
        submitted_this_round = False

        for attempt in range(max_attempts):
            # After a failed form submit, re-fill form fields that postback may have cleared
            if attempt > 0 and submitted_this_round and form_kwargs:
                logger.info("Re-filling form after failed CAPTCHA submission")
                try:
                    await form_handler.fill_form(**form_kwargs)
                except Exception as e:
                    logger.warning("Form re-fill failed: %s — trying CAPTCHA anyway", e)

            # If we never submitted (no candidates), just refresh the CAPTCHA image
            if attempt > 0 and not submitted_this_round:
                await form_handler.refresh_captcha()
            submitted_this_round = False

            # Wait for CAPTCHA image to settle
            await asyncio.sleep(1)

            captcha_img = await form_handler.get_captcha_image()
            last_captcha_img = captcha_img
            img_size = len(captcha_img) if captcha_img else 0
            logger.info("CAPTCHA attempt %d/%d: %d bytes", attempt + 1, max_attempts, img_size)

            if not captcha_img or img_size < 200:
                logger.warning("CAPTCHA image too small or empty — will retry")
                continue

            candidates = await self.captcha_solver.solve(captcha_img)

            if not candidates:
                logger.warning("No candidates for attempt %d/%d", attempt + 1, max_attempts)
                continue

            # Try the best candidate (LLM result is first)
            captcha_text = candidates[0]
            logger.info(
                "Trying CAPTCHA: %r (attempt %d/%d)", captcha_text, attempt + 1, max_attempts
            )
            try:
                submitted_this_round = True
                await form_handler.submit_form(captcha_text)
                logger.info("CAPTCHA accepted: %r", captcha_text)
                return None  # success
            except Exception as e:
                logger.info("CAPTCHA %r rejected: %s", captcha_text, e)

        # Exhausted all retries — try manual callback if available
        if on_captcha and last_captcha_img:
            manual = await on_captcha(last_captcha_img)
            if manual:
                try:
                    await form_handler.submit_form(manual)
                    return None
                except Exception:
                    pass

        return {
            "status": "captcha_required",
            "captcha_image": last_captcha_img,
            "error": "CAPTCHA failed after all retries",
        }


async def _click_continue_button(page) -> bool:
    """
    Click the "पुढे जा" (Go Forward / Continue) button on the disclaimer page.
    Uses an exact Devanagari text match to avoid clicking unrelated buttons.
    Returns True if clicked.
    """
    # Strategy 1: exact JS text match (most reliable — avoids broad 'ज' match)
    try:
        clicked_val = await page.evaluate(f"""
            () => {{
                const target = '{_CONTINUE_BTN_TEXT}';
                const els = Array.from(document.querySelectorAll(
                    'input[type="submit"], input[type="button"], button'
                ));
                for (const el of els) {{
                    const val = (el.value || el.textContent || '').trim();
                    if (val === target && el.offsetParent !== null) {{
                        el.click();
                        return val;
                    }}
                }}
                return null;
            }}
        """)
        if clicked_val:
            logger.info(f"Clicked Continue button via JS exact match: '{clicked_val}'")
            return True
    except Exception as e:
        logger.debug(f"JS exact match for Continue failed: {e}")

    # Strategy 2: known button IDs
    known_ids = [
        "#ContentPlaceHolder1_BtnNextPC",
        "#ContentPlaceHolder1_btnNextPC",
        "#ContentPlaceHolder1_BtnNext",
        "#ContentPlaceHolder1_btnNext",
        "#ContentPlaceHolder1_btnContinue",
        "#ContentPlaceHolder1_BtnContinue",
    ]
    for sel in known_ids:
        try:
            if await page.is_visible(sel, timeout=2000):
                await page.click(sel)
                logger.info(f"Clicked Continue button by ID: {sel}")
                return True
        except Exception:
            continue

    # Strategy 3: contains "पुढे" (partial) — restricted to known safe selectors
    try:
        clicked_val = await page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll(
                    'input[type="submit"], input[type="button"], button'
                ));
                for (const el of els) {
                    const val = (el.value || el.textContent || '').trim();
                    if (val.includes('पुढे') && !val.includes('मागे') && el.offsetParent !== null) {
                        el.click();
                        return val;
                    }
                }
                return null;
            }
        """)
        if clicked_val:
            logger.info(f"Clicked Continue button (partial match): '{clicked_val}'")
            return True
    except Exception:
        pass

    logger.info("No Continue button found — proceeding directly to image capture")
    return False


async def _click_view_link(page) -> bool:
    """
    Click a View/पहा link in a result grid if one is visible.
    Returns True if clicked.
    """
    view_selectors = [
        "a[id*='lnkbtnShowPRCard']",
        "a[id*='lnkbtnView']",
        "a[id*='btnView']",
        "a[id*='lnkView']",
        "a[id*='ShowPR']",
        "a[id*='ViewPR']",
        "input[id*='btnView']",
        "input[value='View']",
        "a:has-text('View')",
        "a:has-text('पहा')",
        "#ContentPlaceHolder1_GridView1 a",
    ]
    for selector in view_selectors:
        try:
            if await page.is_visible(selector, timeout=2000):
                logger.info(f"Clicking View link: {selector}")
                await page.click(selector)
                return True
        except Exception:
            continue
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compatibility shims (used by router.py)
# ─────────────────────────────────────────────────────────────────────────────


def create_browser_service(headless: bool = True):
    return BaseBrowser(headless=headless)


class MahabhumiScraperSelenium(MahabhumiScraper):
    """Async wrapper that looks like the old Selenium class."""

    def __init__(self, browser):
        super().__init__(browser)

    def scrape_pr_card(self, **kwargs):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(super().scrape_pr_card(**kwargs))
        return loop.run_until_complete(super().scrape_pr_card(**kwargs))
