"""
Mahabhumi Bhulekh PR Card Scraper using Selenium.
Uses CDP network interception to capture the actual image URL, then downloads it.

All dropdown options on the site are in Marathi (Devanagari script) with numeric value IDs.
Selection strategy:
  1. Districts  — hardcoded English→value map (36 districts, stable)
  2. Talukas    — AJAX-loaded; fuzzy match against unidecode-romanised Marathi text
  3. Villages   — AJAX-loaded; same fuzzy approach
"""

import base64
import difflib
import io
import json
import logging
import os

# Platform-aware Chrome binary path — only set if the path actually exists
import platform as _platform
import re
import time

import requests
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from unidecode import unidecode

from .captcha_solver import CaptchaSolver

if _platform.system() == "Windows":
    _chrome_candidates = [
        os.path.join(
            os.environ.get("PROGRAMFILES", ""),
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
        ),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
        ),
    ]
    CHROMIUM_BINARY_PATH = next((p for p in _chrome_candidates if os.path.exists(p)), None)
else:
    CHROMIUM_BINARY_PATH = (
        "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
    )

# ------------------------------------------------------------------
# Maharashtra district → numeric dropdown value (stable government IDs)
# ------------------------------------------------------------------
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
    "mumbai": "22",
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

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# JS injected before form submit — intercepts all image requests made by fetch/XHR/img src
_REQUEST_INTERCEPTOR_JS = """
(function() {
    if (window.__prCardInterceptorActive) return;
    window.__prCardInterceptorActive = true;
    window.__capturedImageUrls = [];

    // Intercept fetch
    var _origFetch = window.fetch;
    window.fetch = function() {
        var url = arguments[0];
        if (typeof url === 'string') window.__capturedImageUrls.push(url);
        return _origFetch.apply(this, arguments);
    };

    // Intercept XHR
    var _origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        if (typeof url === 'string') window.__capturedImageUrls.push(url);
        return _origOpen.apply(this, arguments);
    };

    // Intercept <img> src assignments via MutationObserver
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            m.addedNodes.forEach(function(node) {
                if (node.nodeName === 'IMG' && node.src) {
                    window.__capturedImageUrls.push(node.src);
                }
            });
            if (m.type === 'attributes' && m.target.nodeName === 'IMG' &&
                m.attributeName === 'src' && m.target.src) {
                window.__capturedImageUrls.push(m.target.src);
            }
        });
    });
    observer.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['src']});
})();
"""


class SeleniumBrowserService:
    """Browser automation using Selenium with CDP network logging enabled."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None

    def start(self):
        """Start browser with CDP performance logging for network interception."""
        options = Options()

        if self.headless:
            options.add_argument("--headless=new")

        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Docker-specific: allow all URLs and fix common issues
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Enable CDP performance logging so we can capture network image URLs
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        if CHROMIUM_BINARY_PATH:
            options.binary_location = CHROMIUM_BINARY_PATH

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(1920, 1080)
        # Remove implicit wait — we'll use explicit WebDriverWait throughout
        self.driver.implicitly_wait(0)

        # Patch navigator.webdriver to avoid bot detection
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

        logger.info("Browser started with CDP network logging")

    def stop(self):
        """Stop browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        logger.info("Browser stopped")


class MahabhumiScraperSelenium:
    """
    Mahabhumi Bhulekh PR Card scraper.

    Flow:
      1. Navigate to bhulekh.mahabhumi.gov.in
      2. Select District / Taluka / Village by visible text
      3. Select record type (Property Card, 7/12, 8A, K-Prat)
      4. Select search type → enter survey number
      5. Click Search → pick from survey dropdown if shown
      6. Enter mobile + language
      7. Inject JS request interceptor (captures all image URLs from fetch/XHR/img)
      8. Solve CAPTCHA (EasyOCR with multi-variant retry, or return captcha_required)
      9. Submit form
     10. Wait for result page (poll for image element, not blind sleep)
     11. Discover PR card image URL via (priority):
           a) JS interceptor captured URLs
           b) CDP performance log (Network.responseReceived + requestId)
           c) <img> element src attribute (many selectors tried)
     12. Fetch image bytes via CDP Network.getResponseBody (no re-download needed)
         or fall back to requests.get with browser cookies
     13. Save image to outputs/ directory
    """

    BASE_URL = "https://bhulekh.mahabhumi.gov.in"

    RECORD_RADIO_IDS = {
        "7/12": "ContentPlaceHolder1_rbtnSelectType_0",
        "8A": "ContentPlaceHolder1_rbtnSelectType_1",
        "Property Card": "ContentPlaceHolder1_rbtnSelectType_2",
        "K-Prat": "ContentPlaceHolder1_rbtnSelectType_3",
    }

    # Candidate element IDs for the result page PR card image
    _IMG_ELEMENT_IDS = [
        "ContentPlaceHolder1_ImgPC",
        "ContentPlaceHolder1_ImgPropertyCard",
        "ContentPlaceHolder1_Image1",
        "ContentPlaceHolder1_imgPropertyCard",
    ]

    def __init__(self, browser: SeleniumBrowserService):
        self.browser = browser
        self.captcha_solver = CaptchaSolver()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def scrape_pr_card(
        self,
        district: str,
        taluka: str,
        village: str,
        survey_no: str,
        survey_no_part1: str | None,
        mobile: str,
        property_uid: str | None,
        language: str,
        record_of_right: str = "Property Card",
        property_uid_known: bool = False,
    ) -> dict:
        """Full scrape flow. Returns status dict."""
        driver = self.browser.driver
        try:
            logger.info(f"Navigating to {self.BASE_URL} for {record_of_right}")
            # Clear performance logs before navigation
            driver.get_log("performance")
            driver.get(self.BASE_URL)
            self._wait_page_ready(driver)

            return self._fill_and_submit_form(
                driver=driver,
                district=district,
                taluka=taluka,
                village=village,
                survey_no=survey_no,
                survey_no_part1=survey_no_part1,
                mobile=mobile,
                property_uid=property_uid,
                record_of_right=record_of_right,
                language=language,
                property_uid_known=property_uid_known,
            )

        except Exception as e:
            logger.error(f"Scraping failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    def scrape_with_captcha(
        self,
        form_state: dict,
        captcha_value: str,
    ) -> dict:
        """
        Re-run the full form using a saved form_state and a manually supplied captcha.
        Used when auto-OCR failed and the user typed the CAPTCHA themselves.
        """
        driver = self.browser.driver
        try:
            logger.info("Resuming with manual CAPTCHA")
            driver.get_log("performance")
            driver.get(self.BASE_URL)
            self._wait_page_ready(driver)

            return self._fill_and_submit_form(
                driver=driver,
                captcha_override=captcha_value,
                **form_state,
            )
        except Exception as e:
            logger.error(f"CAPTCHA resume failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    # ------------------------------------------------------------------ #
    # Core form flow                                                       #
    # ------------------------------------------------------------------ #

    def _fill_and_submit_form(
        self,
        driver,
        district: str,
        taluka: str,
        village: str,
        survey_no: str,
        survey_no_part1: str | None,
        mobile: str,
        property_uid: str | None,
        record_of_right: str = "Property Card",
        language: str = "EN",
        property_uid_known: bool = False,
        captcha_override: str | None = None,
    ) -> dict:

        wait = WebDriverWait(driver, 20)

        # -- Step 0: Property UID Question -----------------------------------
        logger.info(f"Step 0: Setting UID known to {property_uid_known}")
        uid_radio_id = (
            "ContentPlaceHolder1_rbtnULPIN_0"
            if property_uid_known
            else "ContentPlaceHolder1_rbtnULPIN_1"
        )
        try:
            uid_radio = wait.until(EC.element_to_be_clickable((By.ID, uid_radio_id)))
            driver.execute_script("arguments[0].click();", uid_radio)
            self._wait_ajax(driver, 2)
        except Exception as e:
            logger.warning(f"UID radio not found or clickable: {e}")

        # -- Step 1: Record of Right (radio button) --------------------------
        logger.info(f"Step 1: Selecting record type '{record_of_right}'")
        radio_id = self.RECORD_RADIO_IDS.get(
            record_of_right, self.RECORD_RADIO_IDS["Property Card"]
        )
        try:
            radio = wait.until(EC.element_to_be_clickable((By.ID, radio_id)))
            driver.execute_script("arguments[0].click();", radio)
            self._wait_ajax(driver, 2)
        except TimeoutException:
            logger.warning(f"Radio button {radio_id} not found, skipping")

        # -- Step 2: District ------------------------------------------------
        logger.info(f"Step 2: Selecting district '{district}'")
        wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddlMainDist")))
        self._select_district(driver, district)
        self._wait_ajax(driver, 4)

        # -- Step 3: Taluka --------------------------------------------------
        logger.info(f"Step 3: Selecting taluka '{taluka}'")
        self._wait_options_loaded(driver, "ContentPlaceHolder1_ddlTalForAll")
        self._select_by_fuzzy(driver, "ContentPlaceHolder1_ddlTalForAll", taluka)
        self._wait_ajax(driver, 4)

        # -- Step 4: Village -------------------------------------------------
        logger.info(f"Step 4: Selecting village '{village}'")
        self._wait_options_loaded(driver, "ContentPlaceHolder1_ddlVillForAll")
        self._select_by_fuzzy(driver, "ContentPlaceHolder1_ddlVillForAll", village)
        self._wait_ajax(driver, 3)

        # -- Step 5: Search Type (Survey/Gat Number) -------------------------
        logger.info("Step 5: Selecting search type Survey Number")
        try:
            # rbtnSearchType_0 is Survey Number
            search_type_radio = wait.until(
                EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_rbtnSearchType_0"))
            )
            driver.execute_script("arguments[0].click();", search_type_radio)
            self._wait_ajax(driver, 2)
        except Exception:
            logger.info("Search type radio not found or default")

        # -- Step 6: Survey Number Part 1 + Click Search ---------------------
        logger.info(f"Step 6: Entering survey number part 1 '{survey_no}'")
        # According to user, we fill Survey Number part 1 and hit search button
        survey_input = self._find_element_safe(
            driver,
            [
                "ContentPlaceHolder1_txtcsno",
                "ContentPlaceHolder1_txtSurveyNo",
                "ContentPlaceHolder1_txtPropertyUID",
            ],
        )
        if survey_input:
            survey_input.clear()
            survey_input.send_keys(survey_no)

        logger.info("Step 6b: Clicking Search")
        search_btn = self._find_element_safe(
            driver,
            ["ContentPlaceHolder1_btnsearchfind", "ContentPlaceHolder1_btnSearch"],
        )
        if search_btn:
            driver.execute_script("arguments[0].click();", search_btn)
        self._dismiss_alert(driver)
        self._wait_ajax(driver, 4)

        # -- Step 7: Fill Survey Number (select from dropdown) ---------------
        logger.info("Step 7: Selecting from survey sub-dropdown")
        time.sleep(1.5)
        self._dismiss_alert(driver)

        try:
            survey_dd = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddlsurveyno"))
            )
            survey_select = Select(survey_dd)
            if len(survey_select.options) > 1:
                # If part1 was provided for the dropdown index, use it, else pick first available
                if survey_no_part1:
                    try:
                        survey_select.select_by_index(int(survey_no_part1))
                    except Exception:
                        survey_select.select_by_index(1)
                else:
                    # Pick first non-empty option
                    survey_select.select_by_index(1)
                self._wait_ajax(driver, 2)
        except Exception:
            logger.info("No survey sub-dropdown found or selection failed")

        # -- Step 8: Mobile + Language ---------------------------------------
        logger.info(f"Step 8: Entering mobile '{mobile}'")
        mobile_input = self._find_element_safe(
            driver, ["ContentPlaceHolder1_txtmobile1", "ContentPlaceHolder1_txtMobile"]
        )
        if mobile_input:
            mobile_input.clear()
            mobile_input.send_keys(mobile)

        logger.info(f"Step 8b: Setting language to '{language}'")
        try:
            lang_sel = driver.find_element(By.ID, "ContentPlaceHolder1_ddlLang")
            lang_select = Select(lang_sel)
            lang_idx = 1 if language.upper() == "EN" else 0
            self._select_by_index_safe(lang_select, lang_idx)
        except NoSuchElementException:
            logger.info("Language dropdown not found")
        time.sleep(0.5)

        # -- Step 8c: Inject JS request interceptor --------------------------
        logger.info("Step 8c: Injecting request interceptor")
        try:
            driver.execute_script(_REQUEST_INTERCEPTOR_JS)
        except Exception as e:
            logger.warning(f"Request interceptor injection failed (non-fatal): {e}")

        # -- Step 9: CAPTCHA -------------------------------------------------
        logger.info("Step 9: Handling CAPTCHA")
        captcha_text, captcha_variants, captcha_image_bytes = self._resolve_captcha(
            driver, captcha_override
        )

        if not captcha_text:
            captcha_image_bytes = captcha_image_bytes or self._capture_captcha_image(driver)
            return {
                "status": "captcha_required",
                "captcha_image": captcha_image_bytes,
                "error": "CAPTCHA requires manual input",
            }

        logger.info(f"Trying CAPTCHA: '{captcha_text}' (variants: {captcha_variants})")
        self._set_captcha_value(driver, captcha_text)

        # -- Step 10: Submit -------------------------------------------------
        logger.info("Step 10: Submitting form")
        submit_btn = driver.find_element(By.ID, "ContentPlaceHolder1_btnmainsubmit")
        driver.execute_script(
            "arguments[0].scrollIntoView(true); arguments[0].click();", submit_btn
        )
        self._wait_ajax(driver, 3)

        alert_text = self._dismiss_alert(driver)

        if alert_text and ("correct" in alert_text.lower() or "invalid" in alert_text.lower()):
            logger.info("CAPTCHA rejected, trying variants...")
            success = False
            for variant in captcha_variants[1:]:
                # Refresh CAPTCHA image then try variant
                self._refresh_captcha(driver)
                self._set_captcha_value(driver, variant)
                driver.execute_script(
                    "document.getElementById('ContentPlaceHolder1_btnmainsubmit').click();"
                )
                self._wait_ajax(driver, 3)
                a = self._dismiss_alert(driver)
                if not a or "correct" not in a.lower():
                    success = True
                    break

            if not success:
                captcha_image_bytes = self._capture_captcha_image(driver)
                return {
                    "status": "captcha_required",
                    "captcha_image": captcha_image_bytes,
                    "error": "All CAPTCHA variants rejected — manual input required",
                }

        # -- Step 11: Wait for result page -----------------------------------
        logger.info("Step 11: Waiting for PR card result page")
        self._wait_for_result_page(driver, timeout=30)

        # -- Step 12: Capture PR Card image ----------------------------------
        logger.info("Step 12: Capturing PR Card image")
        return self._capture_pr_card_image(driver)

    # ------------------------------------------------------------------ #
    # Image capture — CDP network interception + fallbacks                #
    # ------------------------------------------------------------------ #

    def _wait_for_result_page(self, driver, timeout: int = 30):
        """
        Wait for the result page to signal readiness.
        Polls for any known result-page indicator: image element, result text, or URL change.
        Falls back to a fixed sleep if nothing is detected within timeout.
        """
        image_locators = [
            (By.ID, "ContentPlaceHolder1_ImgPC"),
            (By.ID, "ContentPlaceHolder1_ImgPropertyCard"),
            (By.CSS_SELECTOR, "img[src*='ShowImage']"),
            (By.CSS_SELECTOR, "img[src*='PropertyCard']"),
            (By.CSS_SELECTOR, "img[src*='GetImage']"),
        ]

        end = time.time() + timeout
        while time.time() < end:
            for by, locator in image_locators:
                try:
                    els = driver.find_elements(by, locator)
                    if els:
                        logger.info(f"Result page ready — found element: {locator}")
                        time.sleep(1)  # brief settle
                        return
                except Exception:
                    pass

            # Also check if navigated to a result URL
            try:
                url = driver.current_url
                if any(kw in url.lower() for kw in ["result", "propertycard", "showimage"]):
                    logger.info(f"Result page ready — URL changed to: {url}")
                    time.sleep(1)
                    return
            except Exception:
                pass

            time.sleep(0.5)

        logger.warning(f"Result page wait timed out after {timeout}s — proceeding anyway")
        time.sleep(2)  # last-resort settle

    def _capture_pr_card_image(self, driver) -> dict:
        """
        Capture the PR Card image using four strategies (in priority order):
          1. JS interceptor — URLs captured by injected fetch/XHR/MutationObserver script
          2. CDP network log — find the image request URL + try Network.getResponseBody
          3. <img> element src — base64 decode or URL download (tries multiple element IDs)
          4. Full-page screenshot fallback
        Returns a dict with keys: status, image_bytes, output_path, image_url
        """
        timestamp = int(time.time())
        output_path = os.path.join(OUTPUT_DIR, f"pr_card_{timestamp}.png")

        # --- Strategy 1: JS interceptor captured URLs -----------------------
        try:
            captured_urls = driver.execute_script("return window.__capturedImageUrls || [];")
            image_url = self._pick_best_image_url(captured_urls)
            if image_url:
                logger.info(f"Found PR card URL via JS interceptor: {image_url}")
                image_bytes = self._fetch_image_bytes(driver, image_url)
                if image_bytes:
                    self._save_image(image_bytes, output_path)
                    return {
                        "status": "completed",
                        "image_bytes": image_bytes,
                        "output_path": output_path,
                        "image_url": image_url,
                    }
        except Exception as e:
            logger.warning(f"JS interceptor strategy failed: {e}")

        # --- Strategy 2: CDP performance log --------------------------------
        image_url, request_id = self._find_image_url_from_network_logs(driver)
        if image_url:
            logger.info(f"Found PR card URL via CDP log: {image_url}")
            # Try CDP getResponseBody first (no re-download needed)
            image_bytes = None
            if request_id:
                image_bytes = self._get_image_bytes_from_cdp(driver, request_id)
            if not image_bytes:
                image_bytes = self._fetch_image_bytes(driver, image_url)
            if image_bytes:
                self._save_image(image_bytes, output_path)
                return {
                    "status": "completed",
                    "image_bytes": image_bytes,
                    "output_path": output_path,
                    "image_url": image_url,
                }

        # --- Strategy 3: <img> element src ----------------------------------
        pc_src = self._find_result_img_src(driver)
        if pc_src:
            logger.info(f"Found ImgPC src (first 80 chars): {pc_src[:80]}")
            if "base64," in pc_src:
                b64_match = re.search(r"base64,(.*)", pc_src)
                if b64_match:
                    image_bytes = base64.b64decode(b64_match.group(1))
                    self._save_image(image_bytes, output_path)
                    return {
                        "status": "completed",
                        "image_bytes": image_bytes,
                        "output_path": output_path,
                        "image_url": "(base64 embedded)",
                    }
            else:
                if pc_src.startswith("/"):
                    pc_src = self.BASE_URL + pc_src
                image_bytes = self._fetch_image_bytes(driver, pc_src)
                if image_bytes:
                    self._save_image(image_bytes, output_path)
                    return {
                        "status": "completed",
                        "image_bytes": image_bytes,
                        "output_path": output_path,
                        "image_url": pc_src,
                    }

        # --- Strategy 4: Full-page screenshot fallback ----------------------
        logger.warning("No PR Card image element found — saving full-page screenshot")
        screenshot = driver.get_screenshot_as_png()
        self._save_image(screenshot, output_path)
        return {
            "status": "completed",
            "image_bytes": screenshot,
            "output_path": output_path,
            "image_url": None,
        }

    def _find_result_img_src(self, driver) -> str | None:
        """
        Search multiple candidate element IDs and CSS selectors for the result image src.
        Returns the first non-empty src found, or None.
        """
        # Try specific known element IDs
        for eid in self._IMG_ELEMENT_IDS:
            src = driver.execute_script(
                "var img = document.getElementById(arguments[0]);"
                "return img && img.src ? img.src : null;",
                eid,
            )
            if src:
                return src

        # Broader search: any img with a URL that looks like a property card
        src = driver.execute_script("""
            var imgs = document.querySelectorAll('img');
            var keywords = ['showimage', 'getimage', 'propertycard', 'prcard', 'propcard'];
            for (var i = 0; i < imgs.length; i++) {
                var s = imgs[i].src || '';
                var sl = s.toLowerCase();
                for (var k of keywords) {
                    if (sl.includes(k) && s.length > 10) return s;
                }
            }
            // Fallback: largest img with a real URL (not data:)
            var best = null, bestW = 0;
            for (var i = 0; i < imgs.length; i++) {
                var s = imgs[i].src || '';
                if (s.startsWith('http') && imgs[i].naturalWidth > bestW) {
                    bestW = imgs[i].naturalWidth;
                    best = s;
                }
            }
            return best;
        """)
        return src or None

    def _pick_best_image_url(self, urls: list) -> str | None:
        """From a list of captured URLs, return the most likely PR card image URL."""
        if not urls:
            return None

        priority_keywords = [
            "showimage",
            "getimage",
            "propertycard",
            "prcard",
            "pr_card",
        ]
        image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]

        candidates = []
        for url in reversed(urls):  # most recent first
            if not isinstance(url, str) or len(url) < 10:
                continue
            url_lower = url.lower()
            # Skip clearly non-image assets
            if any(x in url_lower for x in [".css", ".js", ".ico", ".woff", ".svg"]):
                continue
            is_priority = any(kw in url_lower for kw in priority_keywords)
            is_image_ext = any(url_lower.endswith(ext) for ext in image_extensions)
            is_same_domain = self.BASE_URL in url
            if is_priority:
                return url  # best possible match
            if (is_image_ext or "image" in url_lower) and is_same_domain:
                candidates.append(url)

        return candidates[0] if candidates else None

    def _find_image_url_from_network_logs(self, driver) -> tuple[str | None, str | None]:
        """
        Parse CDP performance logs to find image request URLs.
        Returns (image_url, request_id) or (None, None).
        The request_id can be used with Network.getResponseBody to fetch bytes via CDP.
        """
        try:
            logs = driver.get_log("performance")
            # (priority_score, url, request_id)
            candidates: list[tuple[int, str, str | None]] = []

            priority_keywords = [
                "showimage",
                "getimage",
                "propertycard",
                "prcard",
                "pr_card",
            ]

            for entry in logs:
                try:
                    msg = json.loads(entry["message"]).get("message", {})
                    method = msg.get("method", "")
                    params = msg.get("params", {})

                    if method == "Network.responseReceived":
                        response = params.get("response", {})
                        url = response.get("url", "")
                        mime = response.get("mimeType", "")
                        request_id = params.get("requestId")

                        if self.BASE_URL in url:
                            url_lower = url.lower()
                            score = 0
                            if "image" in mime:
                                score += 2
                            if any(kw in url_lower for kw in priority_keywords):
                                score += 5
                            if any(url_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
                                score += 1
                            if score > 0:
                                candidates.append((score, url, request_id))
                                logger.info(f"CDP image response (score={score}): {url}")

                    elif method == "Network.requestWillBeSent":
                        url = params.get("request", {}).get("url", "")
                        request_id = params.get("requestId")
                        if self.BASE_URL in url:
                            url_lower = url.lower()
                            if any(kw in url_lower for kw in priority_keywords):
                                candidates.append((4, url, request_id))
                            elif any(kw in url_lower for kw in ["image", ".png", ".jpg"]):
                                candidates.append((1, url, request_id))

                except Exception:
                    continue

            if not candidates:
                return None, None

            # Return the highest-scored candidate
            candidates.sort(key=lambda x: x[0], reverse=True)
            best = candidates[0]
            logger.info(f"Best CDP candidate (score={best[0]}): {best[1]}")
            return best[1], best[2]

        except Exception as e:
            logger.error(f"CDP network log parsing failed: {e}")
            return None, None

    def _get_image_bytes_from_cdp(self, driver, request_id: str) -> bytes | None:
        """
        Retrieve image bytes directly from Chrome's network cache via CDP.
        Uses Network.getResponseBody — no additional HTTP request needed.
        """
        try:
            result = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
            body = result.get("body", "")
            if not body:
                return None

            if result.get("base64Encoded", False):
                data = base64.b64decode(body)
            else:
                data = body.encode("latin-1")

            if len(data) > 500:
                logger.info(f"Got {len(data)} bytes via CDP getResponseBody")
                return data
            return None
        except Exception as e:
            logger.debug(f"CDP getResponseBody unavailable (will fall back to download): {e}")
            return None

    def _fetch_image_bytes(self, driver, url: str) -> bytes | None:
        """Download image from URL using the browser's current session cookies."""
        try:
            cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": self.BASE_URL,
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            }
            resp = requests.get(url, cookies=cookies, headers=headers, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 500:
                logger.info(f"Downloaded {len(resp.content)} bytes from {url}")
                return resp.content
            logger.warning(f"Download failed: HTTP {resp.status_code} from {url}")
            return None
        except Exception as e:
            logger.error(f"Image download error: {e}")
            return None

    def _save_image(self, image_bytes: bytes, output_path: str):
        """Save image bytes to the outputs directory."""
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        logger.info(f"Saved PR Card image ({len(image_bytes)} bytes) to: {output_path}")

    # ------------------------------------------------------------------ #
    # CAPTCHA helpers                                                      #
    # ------------------------------------------------------------------ #

    def _resolve_captcha(self, driver, captcha_override: str | None):
        """
        Returns (captcha_text, variants_list, captcha_image_bytes).
        captcha_text is None if resolution failed and manual input is needed.
        """
        if captcha_override:
            return captcha_override, [captcha_override], None

        max_refresh_attempts = 4
        for attempt in range(max_refresh_attempts):
            variants = self._extract_captcha_variants(driver)
            if variants:
                logger.info(f"CAPTCHA OCR variants (attempt {attempt + 1}): {variants}")
                return variants[0], variants, None

            logger.info(f"OCR attempt {attempt + 1} failed, refreshing CAPTCHA...")
            self._refresh_captcha(driver)
            time.sleep(1.5)

        return None, [], self._capture_captcha_image(driver)

    def _extract_captcha_variants(self, driver) -> list:
        """Extract CAPTCHA image and return OCR variants."""
        try:
            captcha_src = driver.execute_script("""
                var img = document.getElementById('ContentPlaceHolder1_captchaImage');
                return img ? img.src : null;
            """)

            if captcha_src and "base64," in captcha_src:
                b64_match = re.search(r"base64,(.*)", captcha_src)
                if b64_match:
                    img_data = base64.b64decode(b64_match.group(1))
                    variants = self.captcha_solver.solve(img_data)
                    if variants:
                        return variants

            # Fallback: crop from screenshot using element position
            image_bytes = self._capture_captcha_image(driver)
            if image_bytes:
                return self.captcha_solver.solve(image_bytes)

            return []

        except Exception as e:
            logger.error(f"CAPTCHA extraction error: {e}")
            return []

    def _capture_captcha_image(self, driver) -> bytes | None:
        """Crop the CAPTCHA from the page using element bounding rect (accurate positioning)."""
        try:
            # Try to get element position from DOM first
            rect = driver.execute_script("""
                var img = document.getElementById('ContentPlaceHolder1_captchaImage');
                if (!img) return null;
                var r = img.getBoundingClientRect();
                return {x: r.left, y: r.top, w: r.width, h: r.height};
            """)

            screenshot = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))
            dpr = driver.execute_script("return window.devicePixelRatio || 1;")

            if rect and rect.get("w", 0) > 10:
                padding = 5
                left = max(0, int(rect["x"] * dpr) - padding)
                top = max(0, int(rect["y"] * dpr) - padding)
                right = int((rect["x"] + rect["w"]) * dpr) + padding
                bottom = int((rect["y"] + rect["h"]) * dpr) + padding
            else:
                # Percentage-based fallback
                w, h = img.size
                left = int(w * 0.38)
                top = int(h * 0.44)
                right = int(w * 0.58)
                bottom = int(h * 0.52)

            cropped = img.crop((left, top, right, bottom))
            buf = io.BytesIO()
            cropped.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            logger.error(f"CAPTCHA capture error: {e}")
            return None

    def _set_captcha_value(self, driver, value: str):
        """Clear and fill the CAPTCHA input field."""
        driver.execute_script(
            "var el = document.getElementById('ContentPlaceHolder1_txtcaptcha');"
            "if (el) { el.value = ''; el.value = arguments[0]; }",
            value,
        )
        time.sleep(0.3)

    def _refresh_captcha(self, driver):
        """Click the CAPTCHA refresh button."""
        try:
            driver.execute_script(
                "var btn = document.getElementById('ContentPlaceHolder1_btnreferesh');"
                "if (btn) btn.click();"
            )
            time.sleep(2)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Dropdown helpers — value-based + fuzzy Marathi matching             #
    # ------------------------------------------------------------------ #

    def _select_district(self, driver, district_english: str):
        """Select district using the hardcoded value map, then Selenium Select for a real click."""
        key = district_english.lower().strip()
        value = DISTRICT_VALUE_MAP.get(key)

        if value:
            sel = Select(driver.find_element(By.ID, "ContentPlaceHolder1_ddlMainDist"))
            sel.select_by_value(value)
            logger.info(f"District '{district_english}' → value '{value}'")
        else:
            logger.warning(f"District '{district_english}' not in map, trying fuzzy…")
            self._select_by_fuzzy(driver, "ContentPlaceHolder1_ddlMainDist", district_english)

    def _select_by_fuzzy(self, driver, element_id: str, query: str):
        """
        Fuzzy-match the query against all dropdown options (handles Marathi text via
        unidecode romanisation) and select the best match using a real Selenium click
        so ASP.NET ViewState is properly committed.
        """
        options: list[tuple[str, str]] = driver.execute_script(
            "return Array.from(document.getElementById(arguments[0]).options)"
            ".map(o => [o.value, o.text.trim()]);",
            element_id,
        )

        q = query.strip()
        q_low = q.lower()
        q_norm = self._norm(q)

        best_value = None
        best_score = 0.0

        for value, text in options:
            if not value or text == "--निवडा--":
                continue

            if text == q:
                best_value = value
                best_score = 1.0
                break
            if text.lower() == q_low:
                best_value = value
                best_score = 1.0
                break
            if q_low in text.lower():
                if best_score < 0.95:
                    best_value = value
                    best_score = 0.95
                continue

            text_norm = self._norm(text)
            score = difflib.SequenceMatcher(None, q_norm, text_norm).ratio()
            if score > best_score:
                best_score = score
                best_value = value

        if not best_value or best_score < 0.5:
            # Last resort: first non-blank option
            best_value, fb_text = next(
                ((v, t) for v, t in options if v and t != "--निवडा--"), (None, None)
            )
            if best_value:
                logger.warning(f"No match for '{query}' in {element_id}, fell back to '{fb_text}'")

        if best_value:
            sel = Select(driver.find_element(By.ID, element_id))
            sel.select_by_value(best_value)
            logger.info(f"Fuzzy matched '{query}' → value '{best_value}' (score {best_score:.2f})")

    @staticmethod
    def _norm(text: str) -> str:
        """
        Normalise text for fuzzy comparison:
          Devanagari → romanised via unidecode → lowercase →
          collapse repeated chars → strip trailing vowels.
        """
        roman = unidecode(text).lower()
        # collapse consecutive identical characters (unidecode doubles many)
        roman = re.sub(r"(.)\1+", r"\1", roman)
        # strip common trailing vowels that vary between English/Marathi spellings
        roman = roman.rstrip("aeiou")
        # remove spaces/punctuation
        roman = re.sub(r"[^a-z0-9]", "", roman)
        return roman

    def _select_by_index_safe(self, sel: Select, index: int):
        if len(sel.options) > index:
            sel.select_by_index(index)

    def _wait_options_loaded(
        self, driver, element_id: str, min_options: int = 2, timeout: int = 15
    ):
        """Wait until a dropdown has at least min_options (AJAX-populated)."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                count = driver.execute_script(
                    "var s=document.getElementById(arguments[0]); return s ? s.options.length : 0;",
                    element_id,
                )
                if count >= min_options:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        logger.warning(f"Timed out waiting for options in {element_id}")

    # ------------------------------------------------------------------ #
    # Misc helpers                                                         #
    # ------------------------------------------------------------------ #

    def _wait_page_ready(self, driver, timeout: int = 15):
        """
        Wait for document.readyState, dismiss the maintenance/custom overlay if present,
        and return a maintenance_mode flag.
        """
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)
        self._dismiss_custom_overlay(driver)

    def _dismiss_custom_overlay(self, driver) -> bool:
        """
        Dismiss any custom HTML alert overlay (e.g., maintenance notifications).
        Returns True if an overlay was found and dismissed.
        Also raises RuntimeError if the overlay signals that services are unavailable.
        """
        overlay_info = driver.execute_script("""
            var ov = document.getElementById('customAlertOverlay');
            if (!ov || ov.style.display === 'none') return null;
            return {
                display: ov.style.display,
                text: ov.innerText || ''
            };
        """)

        if not overlay_info:
            return False

        text = overlay_info.get("text", "")
        logger.info(f"Custom overlay detected: {text[:120]}")

        # Check if it's a maintenance/service-unavailable notice
        maintenance_keywords = [
            "maintenance",
            "scheduled",
            "service",
            "unavailable",
            "देखभाल",
        ]
        is_maintenance = any(kw in text.lower() for kw in maintenance_keywords)

        # Dismiss it (call the page's close function, or hide via JS)
        driver.execute_script("""
            if (typeof closeCustomAlert === 'function') {
                closeCustomAlert();
            } else {
                var ov = document.getElementById('customAlertOverlay');
                if (ov) ov.style.display = 'none';
            }
        """)
        time.sleep(0.5)
        logger.info("Custom overlay dismissed")

        if is_maintenance:
            logger.warning("Site maintenance overlay detected — dismissing and proceeding anyway")

    def _wait_ajax(self, driver, seconds: float):
        """Simple sleep for AJAX-heavy pages; keeps code readable."""
        time.sleep(seconds)

    def _dismiss_alert(self, driver) -> str | None:
        """Accept any JS alert and return its text (or None if no alert)."""
        try:
            alert = driver.switch_to.alert
            text = alert.text
            alert.accept()
            return text
        except NoAlertPresentException:
            return None

    def _find_element_safe(self, driver, ids: list):
        """Try a list of element IDs and return the first one found, or None."""
        for eid in ids:
            try:
                return driver.find_element(By.ID, eid)
            except NoSuchElementException:
                continue
        return None


def create_browser_service(headless: bool = False) -> SeleniumBrowserService:
    """Create and start browser service."""
    service = SeleniumBrowserService(headless=headless)
    service.start()
    return service
