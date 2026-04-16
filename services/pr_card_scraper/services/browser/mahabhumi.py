import logging
import asyncio
import difflib
import re
from typing import Optional
from unidecode import unidecode
from playwright.async_api import Page, TimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Common English→Marathi transliterations for village/taluka names.
# The site dropdowns are in Marathi; when a user supplies an English name we map it first.
ENGLISH_TO_MARATHI = {
    # Pune talukas
    "haveli": "हवेली",
    "pune city": "पुणे शहर",
    "purandar": "पुरंदर",
    "maval": "मावळ",
    "mulshi": "मुळशी",
    "bhor": "भोर",
    "velha": "वेल्हा",
    "indapur": "इंदापुर",
    "junnar": "जुन्नर",
    "daund": "दौंड",
    "khed": "खेड",
    "ambegaon": "आंबेगाव",
    "baramati": "बारामती",
    "shirur": "शिरुर",
    # Common Pune villages
    "baner": "बाणेर",
    "kothrud": "कोथरूड",
    "wakad": "वाकड",
    "hinjewadi": "हिंजवडी",
    "aundh": "औंध",
    "pimple saudagar": "पिंपळे सौदागर",
    "pimple nilakh": "पिंपळे निलख",
    "pashan": "पाषाण",
    "bavdhan": "बावधन",
    "sus": "सस",
    "maan": "माण",
    "nande": "नांदे",
    "mahalunge": "महाळुंगे",
    "pirangut": "पिरंगुट",
    "bhugaon": "भुगाव",
    "lavale": "लवाळे",
    "shivane": "शिवणे",
    "narhe": "नऱ्हे",
    "dhayari": "धायरी",
    "ambegaon budruk": "आंबेगाव बु.",
    "hadapsar": "हडपसर",
    "fursungi": "फुरसुंगी",
    "uruli kanchan": "उरुळी कांचन",
    "uruli devachi": "उरुळी देवाची",
    "wagholi": "वाघोली",
    "lohegaon": "लोहगाव",
    "kharadi": "खराडी",
    "manjari": "मांजरी",
    "undri": "उंड्री",
    "pisoli": "पिसोळी",
    "kondhwa budruk": "कोंढवे बु.",
    "katraj": "कात्रज",
    "ambegaon pathar": "आंबेगाव पठार",
    "theur": "थेऊर",
}

DISTRICT_VALUE_MAP = {
    "nandurbar": "1",
    "dhule": "2",
    "jalgaon": "3",
    "buldhana": "4",
    "akola": "5",
    "washim": "6",
    "amravati": "7",
    "wardha": "8",
    "nagpur": "9",
    "bhandara": "10",
    "gondia": "11",
    "gadchiroli": "12",
    "chandrapur": "13",
    "yavatmal": "14",
    "nanded": "15",
    "hingoli": "16",
    "parbhani": "17",
    "jalna": "18",
    "aurangabad": "19",
    "chhatrapati sambhajinagar": "19",
    "sambhajinagar": "19",
    "nashik": "20",
    "thane": "21",
    "mumbai suburban": "22",
    "mumbai city": "23",
    "mumbai": "23",
    "raigad": "24",
    "pune": "25",
    "ahmednagar": "26",
    "ahilyanagar": "26",
    "beed": "27",
    "latur": "28",
    "dharashiv": "29",
    "osmanabad": "29",
    "solapur": "30",
    "satara": "31",
    "ratnagiri": "32",
    "sindhudurg": "33",
    "kolhapur": "34",
    "sangli": "35",
    "palghar": "36",
}


class MahabhumiFormHandler:
    """Handles interaction with Mahabhumi Bhulekh website forms based on full user workflow."""

    BASE_URL = "https://bhulekh.mahabhumi.gov.in"

    RECORD_RADIO_IDS = {
        "7/12": "ContentPlaceHolder1_rbtnSelectType_0",
        "8A": "ContentPlaceHolder1_rbtnSelectType_1",
        "Property Card": "ContentPlaceHolder1_rbtnSelectType_2",
        "K-Prat": "ContentPlaceHolder1_rbtnSelectType_3",
    }

    def __init__(self, page: Page):
        self.page = page

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def navigate_to_base(self):
        """Navigate to the base URL with retries.

        Uses 'domcontentloaded' (not 'networkidle') because the Bhulekh site
        loads many slow third-party resources that prevent networkidle from
        being reached within a reasonable timeout.
        """
        logger.info(f"Navigating to {self.BASE_URL}")
        try:
            # Clear storage/cookies to avoid session conflicts
            context = self.page.context
            await context.clear_cookies()

            try:
                await self.page.goto(
                    self.BASE_URL, wait_until="domcontentloaded", timeout=45000
                )
            except Exception:
                # Last-resort: commit=True means the navigation was initiated
                await self.page.goto(
                    self.BASE_URL, wait_until="commit", timeout=30000
                )

            # Give the page JS a moment to wire up before we start clicking
            await asyncio.sleep(3)
            await self._dismiss_overlays()
        except Exception as e:
            logger.warning(f"Navigation attempt failed: {e}")
            raise e

    async def _wait_for_loading(self):
        """Wait for ASP.NET UpdatePanel / overlays to settle."""
        await asyncio.sleep(0.5)
        # Only wait on selectors that actually exist; presence-check first avoids
        # the cost of a timeout on every call when the overlay is absent.
        for selector in ("#customAlertOverlay", ".loading"):
            try:
                if await self.page.locator(selector).count() > 0:
                    await self.page.wait_for_selector(selector, state="hidden", timeout=5000)
            except Exception:
                pass
        try:
            await self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await asyncio.sleep(0.3)

    async def _fire_change(self, selector: str):
        """
        Fire a change event that ASP.NET UpdatePanel will respond to.
        Covers: native bubbling event, jQuery trigger, and direct onchange invocation.
        """
        await self.page.evaluate("""
            selector => {
                const el = document.querySelector(selector);
                if (!el) return;
                // 1. Native bubbling change event (jQuery listens on bubbling)
                el.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                // 2. jQuery trigger if loaded
                if (typeof $ !== 'undefined') { try { $(el).trigger('change'); } catch(e) {} }
                // 3. ASP.NET __doPostBack embedded in onchange attribute
                if (el.onchange) { try { el.onchange(); } catch(e) {} }
            }
        """, selector)

    async def _select_with_retry(self, selector: str, value: str, label: Optional[str] = None):
        """Select an option and retry if the value doesn't stick or dropdown is empty."""
        for attempt in range(3):
            try:
                # Wait for options to load
                await self.page.wait_for_function(
                    f"selector => document.querySelectorAll(selector + ' option').length > 1",
                    arg=selector,
                    timeout=20000
                )

                if label:
                    await self.page.select_option(selector, label=label)
                else:
                    await self.page.select_option(selector, value=value)

                await self._fire_change(selector)
                await self._wait_for_loading()
                await asyncio.sleep(2)

                # Verify selection
                new_val = await self.page.eval_on_selector(selector, "el => el.value")
                if new_val != "0" and (not value or new_val == value):
                    return True
            except Exception as e:
                logger.warning(f"Selection failed for {selector} on attempt {attempt+1}: {e}")
                await asyncio.sleep(3)
        return False

    async def fill_form(
        self,
        district: str,
        taluka: str,
        village: str,
        survey_no: str,
        survey_no_part1: Optional[str],
        mobile: str,
        record_of_right: str = "Property Card",
        language: str = "EN",
        property_uid_known: bool = False,
        # Alias accepted so callers using the old name don't break
        know_property_uid: bool = False,
    ):
        """Fill the main form steps following user's exact flow:
        UID radio → Record type → District → Taluka → Village →
        Search type → Survey No (Part-1) → Search → Select result →
        Mobile → Language → (captcha + submit handled by caller)
        """

        # Step 1: Property UID Knowledge (default: No)
        logger.info("Do you know Property UID? No")
        uid_radio_id = "ContentPlaceHolder1_rbtnULPIN_1"
        await self.page.click(f"#{uid_radio_id}")
        await self._wait_for_loading()
        await asyncio.sleep(1)

        # Step 2: Select Record Type
        logger.info(f"Selecting record type: {record_of_right}")
        radio_id = self.RECORD_RADIO_IDS.get(record_of_right, self.RECORD_RADIO_IDS["Property Card"])
        await self._dismiss_overlays()
        await self.page.click(f"#{radio_id}", force=True)
        await self._wait_for_loading()
        await asyncio.sleep(1.5)

        # Step 3: District
        logger.info(f"Selecting district: {district}")
        dist_val = DISTRICT_VALUE_MAP.get(district.lower())
        if dist_val:
            await self._select_with_retry("#ContentPlaceHolder1_ddlMainDist", dist_val)
        else:
            await self._select_fuzzy("#ContentPlaceHolder1_ddlMainDist", district)

        # Step 4: Taluka — translate English→Marathi if a known mapping exists
        taluka_marathi = ENGLISH_TO_MARATHI.get(taluka.lower(), taluka)
        logger.info(f"Selecting taluka: {taluka} (lookup: '{taluka_marathi}')")
        await self._select_fuzzy("#ContentPlaceHolder1_ddlTalForAll", taluka_marathi)

        # Re-verify Taluka
        tal_val = await self.page.eval_on_selector("#ContentPlaceHolder1_ddlTalForAll", "el => el.value")
        if not tal_val or tal_val == "0":
            logger.warning("Taluka selection lost! Retrying with original name...")
            await self._select_fuzzy("#ContentPlaceHolder1_ddlTalForAll", taluka)

        # Step 5: Village — translate English→Marathi if a known mapping exists
        village_marathi = ENGLISH_TO_MARATHI.get(village.lower(), village)
        logger.info(f"Selecting village: {village} (lookup: '{village_marathi}')")
        await self._select_fuzzy("#ContentPlaceHolder1_ddlVillForAll", village_marathi)

        # Re-verify Village — retry with Marathi name first, then English as last resort
        vill_val = await self.page.eval_on_selector("#ContentPlaceHolder1_ddlVillForAll", "el => el.value")
        if not vill_val or vill_val == "0":
            logger.warning("Village selection failed! Retrying with Marathi name...")
            await self._select_fuzzy("#ContentPlaceHolder1_ddlVillForAll", village_marathi)

        # Step 6: Select Search Type → Survey/Gat Number (value "1")
        logger.info("Setting search type to Survey/Gat Number")
        await self._select_with_retry("#ContentPlaceHolder1_ddlSelectSearchType", "1")

        # Step 7: Fill Survey Number / CTS Number (Part-1) field and click Search
        # survey_no_part1 overrides survey_no when provided; otherwise survey_no is used as Part-1
        search_value = survey_no_part1 if survey_no_part1 else survey_no
        logger.info(f"Entering survey/CTS number (Part-1): {search_value}")
        filled_manually = False
        await asyncio.sleep(1)  # let form react to search-type change

        # --- Debug: log all visible input IDs on the page ---
        try:
            visible_inputs = await self.page.evaluate("""
                () => Array.from(document.querySelectorAll('input[type="text"], select'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => el.id || el.name || '(no-id)')
            """)
            logger.info(f"Visible inputs after search-type selection: {visible_inputs}")
        except Exception:
            pass

        try:
            # Only use the dropdown if it has actual options loaded (>1 means real data beyond placeholder)
            ddl_option_count = await self.page.evaluate("""
                () => {
                    const el = document.querySelector('#ContentPlaceHolder1_ddlsurveyno');
                    return el ? el.options.length : 0;
                }
            """)
            if ddl_option_count > 1:
                logger.info(f"Survey dropdown has {ddl_option_count} options — selecting via dropdown")
                await self._select_fuzzy("#ContentPlaceHolder1_ddlsurveyno", search_value)
                filled_manually = False  # dropdown path: no Search button click needed
            else:
                # Text-input path: type into CTS/survey text box and click Search
                # IDs ordered from most-common to least-common on Bhulekh Property Card form
                cts_selectors = [
                    "#ContentPlaceHolder1_txtSurveyNoNew",
                    "#ContentPlaceHolder1_txtcsno",
                    "#ContentPlaceHolder1_txtCTSNo",
                    "#ContentPlaceHolder1_txtCTSNO",
                    "#ContentPlaceHolder1_txtSurveyNo",
                    "#ContentPlaceHolder1_txtGatNo",
                    "#ContentPlaceHolder1_txtPCNumber",
                    "#ContentPlaceHolder1_txtSatNo",
                ]
                for sel in cts_selectors:
                    try:
                        if await self.page.is_visible(sel, timeout=2000):
                            await self.page.click(sel)
                            await self.page.keyboard.press("Control+A")
                            await self.page.keyboard.press("Backspace")
                            await self.page.keyboard.type(search_value, delay=100)
                            logger.info(f"Entered survey/CTS number '{search_value}' in {sel}")
                            filled_manually = True
                            break
                    except Exception:
                        continue

                if not filled_manually:
                    # Last resort: JS injection into first visible text input that isn't mobile/captcha
                    filled_manually = await self.page.evaluate("""
                        (val) => {
                            const exclude = ['mobile', 'Mobile', 'captcha', 'Captcha', 'lang', 'Lang'];
                            const inputs = Array.from(document.querySelectorAll('input[type="text"]'))
                                .filter(el => {
                                    if (el.offsetParent === null) return false;
                                    const id = el.id || '';
                                    return !exclude.some(kw => id.includes(kw));
                                });
                            if (inputs.length > 0) {
                                inputs[0].focus();
                                inputs[0].value = val;
                                inputs[0].dispatchEvent(new Event('input', {bubbles:true}));
                                inputs[0].dispatchEvent(new Event('change', {bubbles:true}));
                                return inputs[0].id || '(first-visible-input)';
                            }
                            return null;
                        }
                    """, search_value)
                    if filled_manually:
                        logger.info(f"Entered survey/CTS number via JS fallback into: {filled_manually}")
                        filled_manually = True  # convert the returned id string to truthy bool

        except Exception as e:
            logger.warning(f"Error entering survey/CTS number: {e}")

        # Step 7b: Click Search button (text-input path only)
        if filled_manually:
            search_btns = [
                "#ContentPlaceHolder1_btnSearch",
                "#ContentPlaceHolder1_btnsearchfind",
                "#ContentPlaceHolder1_btnSearchPR",
                "input[value='Search']",
                "input[id*='Search'][type='submit']",
                "input[id*='Search'][type='button']",
            ]
            clicked_search = False
            for btn in search_btns:
                try:
                    if await self.page.is_visible(btn, timeout=2000):
                        await self.page.click(btn)
                        await self._wait_for_loading()
                        await asyncio.sleep(1.5)
                        clicked_search = True
                        logger.info(f"Clicked search button: {btn}")
                        break
                except Exception:
                    continue

            if clicked_search:
                # Step 7c: Select the survey number from the result dropdown/grid.
                # After Search, the site populates either a dropdown with matching records
                # or a grid. We must pick the right row before proceeding.
                await self._select_survey_from_results(survey_no)

        # Step 8: Mobile
        logger.info(f"Entering mobile: {mobile}")
        mobile_selectors = ["#ContentPlaceHolder1_txtmobile1", "#ContentPlaceHolder1_txtMobile"]
        for selector in mobile_selectors:
            try:
                if await self.page.is_visible(selector, timeout=3000):
                    await self.page.click(selector)
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")
                    await self.page.keyboard.type(mobile, delay=50)
                    await self.page.keyboard.press("Tab")
                    # Solidify via JS so ASP.NET validators pick it up
                    await self.page.evaluate(
                        """(sel, val) => {
                            const el = document.querySelector(sel);
                            if (el) {
                                el.value = val;
                                el.dispatchEvent(new Event('input', {bubbles:true}));
                                el.dispatchEvent(new Event('change', {bubbles:true}));
                                el.dispatchEvent(new Event('blur', {bubbles:true}));
                            }
                        }""",
                        selector, mobile,
                    )
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue

        # Step 9: Language (must come AFTER mobile — per site flow)
        logger.info(f"Setting language to: {language}")
        lang_val = "en_in" if language.upper() == "EN" else "mr_in"
        try:
            await self._select_with_retry("#ContentPlaceHolder1_ddllangforAll", lang_val)
        except Exception as e:
            logger.warning(f"Language selection failed (non-fatal): {e}")

    async def _select_survey_from_results(self, survey_no: str):
        """After clicking Search, select the matching survey number from results.

        The site may show either:
          a) A dropdown (#ContentPlaceHolder1_ddlsurveyno) that gets populated
          b) A GridView table with clickable links / rows
        Both are handled here. If neither appears, we log and continue so the
        rest of the flow can still attempt submission.
        """
        await asyncio.sleep(2)

        # Path A: result dropdown populated after Search
        try:
            visible = await self.page.is_visible("#ContentPlaceHolder1_ddlsurveyno", timeout=5000)
            if visible:
                opt_count = await self.page.evaluate(
                    "() => document.querySelectorAll('#ContentPlaceHolder1_ddlsurveyno option').length"
                )
                if opt_count > 1:
                    logger.info(f"Survey result dropdown appeared with {opt_count} options — selecting '{survey_no}'")
                    await self._select_fuzzy("#ContentPlaceHolder1_ddlsurveyno", survey_no)
                    return
        except Exception:
            pass

        # Path B: GridView table — click the first matching row or View link
        grid_selectors = [
            "#ContentPlaceHolder1_GridView1",
            "table.grid",
            "table[id*='Grid']",
        ]
        for grid_sel in grid_selectors:
            try:
                if not await self.page.is_visible(grid_sel, timeout=3000):
                    continue

                # Try to find a row whose text matches the survey number
                clicked = await self.page.evaluate(
                    """(gridSel, surveyNo) => {
                        const grid = document.querySelector(gridSel);
                        if (!grid) return false;
                        const rows = Array.from(grid.querySelectorAll('tr'));
                        for (const row of rows) {
                            if (row.textContent.includes(surveyNo)) {
                                // Prefer an anchor/button in this row
                                const link = row.querySelector('a, input[type="submit"], input[type="button"]');
                                if (link) { link.click(); return true; }
                                row.click();
                                return true;
                            }
                        }
                        // Fallback: click first data row (skip header)
                        const firstDataRow = rows[1];
                        if (firstDataRow) {
                            const link = firstDataRow.querySelector('a, input[type="submit"], input[type="button"]');
                            if (link) { link.click(); return true; }
                            firstDataRow.click();
                            return true;
                        }
                        return false;
                    }""",
                    grid_sel, survey_no,
                )
                if clicked:
                    logger.info(f"Selected survey from GridView: '{survey_no}'")
                    await self._wait_for_loading()
                    await asyncio.sleep(2)
                    return
            except Exception:
                continue

        logger.warning(f"Could not find survey result selector for '{survey_no}' — continuing anyway")

    async def _dismiss_overlays(self):
        """Dismiss any custom alert overlays."""
        try:
            overlays = [
                "#customAlertOverlay",
                ".custom-alert-overlay",
                ".modal-backdrop",
            ]
            for selector in overlays:
                isVisible = await self.page.locator(selector).is_visible()
                if isVisible:
                    logger.info(f"Dismissing overlay: {selector}")
                    close_btn = await self.page.query_selector(
                        f"{selector} button, {selector} .close, {selector} #btnOk"
                    )
                    if close_btn:
                        await close_btn.click()
                    else:
                        await self.page.evaluate(
                            "selector => { const el = document.querySelector(selector); if(el) el.style.display = 'none'; }",
                            selector,
                        )
        except Exception:
            pass

    async def _save_debug_screenshot(self, label: str):
        """Save a debug screenshot to outputs/ for post-mortem inspection."""
        try:
            import os, time
            out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
            os.makedirs(out, exist_ok=True)
            path = os.path.join(out, f"debug_{label}_{int(time.time())}.png")
            await self.page.screenshot(path=path, full_page=True)
            logger.info(f"Debug screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Debug screenshot failed: {e}")

    async def _select_fuzzy(self, selector: str, target_text: str, timeout: int = 45000):
        """Select option using fuzzy matching on Marathi text."""
        try:
            # Wait for dropdown to have more than 1 option (not just 'Select')
            await self.page.wait_for_function(
                "selector => document.querySelectorAll(selector + ' option').length > 1",
                arg=selector,
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning(f"Dropdown {selector} options did not load in time")
            await self._save_debug_screenshot(f"timeout_{selector.replace('#','').replace('_','-')}")
            return

        options = await self.page.eval_on_selector_all(
            f"{selector} option",
            "options => options.map(o => ({text: o.innerText, value: o.value}))",
        )

        target_norm = self._norm(target_text)
        best_val = None
        best_score = 0
        best_text = ""

        for opt in options:
            if not opt["value"] or opt["value"] == "0":
                continue
            opt_norm = self._norm(opt["text"])

            # Also match against just the place name (last segment after comma).
            # Bhulekh Property Card talukas are "उप अधीक्षक भूमि अभिलेख, हवेली" —
            # matching only against "हवेली" gives far better accuracy.
            opt_place_raw = opt["text"].split(",")[-1].strip()
            opt_place = self._norm(opt_place_raw)

            # Full-string score
            score = difflib.SequenceMatcher(None, target_norm, opt_norm).ratio()
            if target_norm in opt_norm or opt_norm in target_norm:
                score += 0.2

            # Place-name score (weighted higher)
            place_score = difflib.SequenceMatcher(None, target_norm, opt_place).ratio()
            if target_norm in opt_place or opt_place in target_norm:
                place_score += 0.3

            score = max(score, place_score)

            if score > best_score:
                best_score = score
                best_val = opt["value"]
                best_text = opt["text"]

        # Always log top matches to help with debugging
        all_opts = [o["text"].strip() for o in options if o["value"] and o["value"] != "0"]
        logger.debug(f"Available options in {selector} ({len(all_opts)}): {all_opts[:30]}")

        if not best_val or best_score <= 0.3:
            logger.warning(
                f"No match for '{target_text}' in {selector} (best score: {best_score:.2f}). "
                f"Available ({len(all_opts)}): {all_opts[:20]}"
            )
            return

        if best_val and best_score > 0.3:
            logger.info(
                f"Fuzzy match: '{target_text}' -> '{best_text}' (score: {best_score:.2f})"
            )
            await self.page.select_option(selector, best_val)
            await self._fire_change(selector)
            await self._wait_for_loading()
            await asyncio.sleep(2)

    @staticmethod
    def _norm(text: str) -> str:
        roman = unidecode(text).lower()
        roman = re.sub(r"(.)\1+", r"\1", roman)
        roman = roman.rstrip("aeiou")
        roman = re.sub(r"[^a-z0-9]", "", roman)
        return roman

    async def get_captcha_image(self) -> bytes:
        """Capture CAPTCHA image bytes and save a debug copy to outputs/."""
        captcha_loc = self.page.locator("#ContentPlaceHolder1_captchaImage")
        await captcha_loc.wait_for(state="visible")
        try:
            img_bytes = await captcha_loc.screenshot(timeout=5000)
        except Exception as e:
            logger.warning(f"Element screenshot failed ({e}), trying JS extraction")
            b64 = await self.page.evaluate('''() => {
                const img = document.querySelector("#ContentPlaceHolder1_captchaImage");
                const canvas = document.createElement("canvas");
                canvas.width = img.width || img.naturalWidth || 200;
                canvas.height = img.height || img.naturalHeight || 50;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                return canvas.toDataURL("image/png").split(",")[1];
            }''')
            import base64
            img_bytes = base64.b64decode(b64)

        # Save debug copy so we can check what the OCR is reading
        try:
            import os, time
            out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
            os.makedirs(out, exist_ok=True)
            path = os.path.join(out, f"captcha_{int(time.time())}.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            logger.info(f"CAPTCHA image saved for inspection: {path}")
        except Exception:
            pass

        return img_bytes

    async def refresh_captcha(self):
        """Click the CAPTCHA refresh button to get a new image."""
        refresh_selectors = [
            "#ContentPlaceHolder1_btnRefreshCaptcha",
            "#ContentPlaceHolder1_lnkRefresh",
            "a:has-text('Refresh')",
            "img[alt*='refresh']",
            "[onclick*='captcha']",
        ]
        for sel in refresh_selectors:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    logger.info("Refreshed CAPTCHA via %s", sel)
                    await asyncio.sleep(2)
                    return
            except Exception:
                continue
        # Fallback: just reload the captcha image element
        try:
            await self.page.evaluate('''() => {
                const img = document.querySelector("#ContentPlaceHolder1_captchaImage");
                if (img) img.src = img.src + "?" + Date.now();
            }''')
            logger.info("Refreshed CAPTCHA via src reload")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning("Could not refresh CAPTCHA: %s", e)

    async def submit_form(self, captcha_text: str):
        """Fill CAPTCHA and submit the form. Raises if a validation dialog appears."""
        await self.page.fill("#ContentPlaceHolder1_txtcaptcha", captcha_text)

        self._last_dialog_message = None

        async def handle_dialog(dialog):
            self._last_dialog_message = dialog.message
            logger.info(f"Post-submit dialog: {dialog.message}")
            await dialog.accept()

        self.page.on("dialog", handle_dialog)

        try:
            await self.page.click("#ContentPlaceHolder1_btnmainsubmit")
            await asyncio.sleep(5)
            await self._save_debug_screenshot("after_submit")

            # Check if the dialog was a validation error (not a success message)
            if self._last_dialog_message:
                msg = self._last_dialog_message.lower()
                # Marathi validation errors
                is_validation_error = any(
                    kw in msg
                    for kw in [
                        "निवडा",
                        "select",
                        "enter",
                        "correct",
                        "invalid",
                        "captcha",
                        "कृपया",
                        "भरा",
                        "wrong",
                        "not found",
                        "सापडले नाही",
                        "error6",
                        "try again"
                    ]
                )
                if is_validation_error:
                    raise RuntimeError(
                        f"Form validation error: {self._last_dialog_message}"
                    )
        finally:
            self.page.remove_listener("dialog", handle_dialog)
