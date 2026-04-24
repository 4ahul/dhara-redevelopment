#!/usr/bin/env python3
"""
PR Card Scraper Watchdog
========================
Polls bhulekh.mahabhumi.gov.in every POLL_INTERVAL seconds.
The moment the site is accessible (no Runtime Error), it launches
a full Selenium scrape, captures the PR card image URL via CDP/JS
interceptor, downloads the image, and saves it to outputs/.

Runs continuously until:
  - A PR card image is successfully saved  (exit 0)
  - MAX_RUNTIME_HOURS is exceeded          (exit 1)

Resilient to:
  - Site maintenance overlays (auto-dismissed by scraper)
  - CAPTCHA (EasyOCR with up to CAPTCHA_RETRIES refreshes)
  - Network hiccups during polling
  - ChromeDriver crashes (fresh browser per attempt)
"""

import sys
import os
import time
import json
import logging
import requests
from datetime import datetime, timedelta

# ── Make service modules importable ──────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

BASE_URL = "https://bhulekh.mahabhumi.gov.in"
POLL_INTERVAL = 300  # seconds between site-up checks (5 min)
SCRAPE_TIMEOUT = 600  # seconds allowed per scrape attempt (10 min)
CAPTCHA_RETRIES = 5  # CAPTCHA refresh + EasyOCR retries per scrape
MAX_RUNTIME_HOURS = 96  # give up after 4 days (maintenance ends Apr 5)
HEADLESS = True  # run Chrome headlessly

# ── Targets to try (in order, first success wins) ───────────────────────────
# Derived from debug screenshots: Pune / Haveli / Kothrud / 7-12 was being tested.
# Multiple fallbacks added for resilience.
TARGETS = [
    # Primary — confirmed from debug screenshots
    dict(
        district="pune",
        taluka="Haveli",
        village="Kothrud",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
    dict(
        district="pune",
        taluka="Haveli",
        village="Kothrud",
        survey_no="2",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
    dict(
        district="pune",
        taluka="Haveli",
        village="Kothrud",
        survey_no="5",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
    # Property Card variant (urban Pune)
    dict(
        district="pune",
        taluka="Pune City",
        village="Kasba Peth",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="Property Card",
        language="EN",
        property_uid=None,
    ),
    dict(
        district="pune",
        taluka="Pune City",
        village="Shivajinagar",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="Property Card",
        language="EN",
        property_uid=None,
    ),
    # Haveli 7/12 with different villages
    dict(
        district="pune",
        taluka="Haveli",
        village="Baner",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
    dict(
        district="pune",
        taluka="Haveli",
        village="Wadgaon Sheri",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
    # Nashik fallback
    dict(
        district="nashik",
        taluka="Nashik",
        village="Nashik",
        survey_no="1",
        survey_no_part1=None,
        mobile="9999999999",
        record_of_right="7/12",
        language="EN",
        property_uid=None,
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════════════════════

OUTPUT_DIR = os.path.join(_HERE, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

_RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(OUTPUT_DIR, f"watchdog_{_RUN_TS}.log")
STATUS_FILE = os.path.join(OUTPUT_DIR, "watchdog_status.json")

# ═══════════════════════════════════════════════════════════════════════════
#  Logging — UTF-8 everywhere to handle Marathi/Unicode in log output
# ═══════════════════════════════════════════════════════════════════════════


class _Utf8StreamHandler(logging.StreamHandler):
    """StreamHandler that never crashes on non-ASCII characters."""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.buffer.write(
                (msg + self.terminator).encode("utf-8", errors="replace")
            )
            stream.buffer.flush()
        except Exception:
            self.handleError(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        _Utf8StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("watchdog")


# ═══════════════════════════════════════════════════════════════════════════
#  Status persistence
# ═══════════════════════════════════════════════════════════════════════════


def _write_status(data: dict):
    data["updated_at"] = datetime.now().isoformat()
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  Site probe — lightweight HTTP check (no browser)
# ═══════════════════════════════════════════════════════════════════════════

_PROBE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _site_is_up() -> bool:
    """
    Returns True if bhulekh.mahabhumi.gov.in looks operational.

    Strategy:
      1. Quick requests probe (45 s timeout). If we get a 200 without
         "Runtime Error" in the body the site is up.
      2. If requests times out (the site is very slow even for Chrome),
         do a lightweight Chrome probe to check form element presence.
    """
    # -- Stage 1: Fast requests probe ------------------------------------
    try:
        resp = requests.get(
            BASE_URL,
            headers=_PROBE_HEADERS,
            timeout=45,
            allow_redirects=True,
            verify=False,
        )
        if resp.status_code >= 500:
            logger.debug(f"Probe HTTP {resp.status_code} — server error")
            return False
        body = resp.text[:3000]
        if "Runtime Error" in body or "Server Error in" in body:
            logger.debug("Probe: ASP.NET Runtime/Server Error in body")
            return False
        if "ContentPlaceHolder1_ddlMainDist" in body or "ddlMainDist" in body:
            logger.info("Probe: district dropdown found in HTML — form is live!")
            return True
        if resp.status_code == 200:
            logger.info("Probe: HTTP 200 without Runtime Error — treating as up")
            return True
        return False
    except requests.exceptions.Timeout:
        logger.debug("Probe stage-1 timed out (>45 s) — falling back to Chrome probe")
    except Exception as e:
        logger.debug(f"Probe stage-1 exception: {e}")

    # -- Stage 2: Chrome headless probe (only if requests timed out) ------
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,800")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        drv = webdriver.Chrome(options=opts)
        drv.implicitly_wait(0)
        try:
            drv.get(BASE_URL)
            WebDriverWait(drv, 40).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            import time as _t

            _t.sleep(2)
            title = drv.title or ""
            dist_el = drv.execute_script(
                "return document.getElementById('ContentPlaceHolder1_ddlMainDist');"
            )
            is_error = "Runtime Error" in title or "Server Error" in title
            form_present = dist_el is not None
            logger.debug(
                f"Chrome probe: title={title!r} form_present={form_present} error={is_error}"
            )
            return form_present and not is_error
        finally:
            try:
                drv.quit()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Probe stage-2 Chrome exception: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  Single scrape attempt (one target, fresh browser)
# ═══════════════════════════════════════════════════════════════════════════


def _run_scrape(target: dict) -> dict:
    from services.pr_card_scraper.services.browser import create_browser_service, MahabhumiScraperSelenium

    browser = None
    try:
        browser = create_browser_service(headless=HEADLESS)
        scraper = MahabhumiScraperSelenium(browser)
        return scraper.scrape_pr_card(**target)
    except Exception as exc:
        logger.error(f"Scrape exception: {exc}")
        return {"status": "failed", "error": str(exc)}
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
#  Save result
# ═══════════════════════════════════════════════════════════════════════════


def _persist_image(result: dict, target: dict) -> str:
    """Save the PR card image to outputs/ and return the file path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = result.get("output_path", "")
    image_bytes = None

    # 1. Use existing file from scraper
    if out_path and os.path.exists(out_path):
        with open(out_path, "rb") as f:
            image_bytes = f.read()
        final_path = out_path
    else:
        # 2. Use image_bytes from result dict
        image_bytes = result.get("image_bytes", b"")
        final_path = os.path.join(
            OUTPUT_DIR,
            f"pr_card_FINAL_{target['district']}_{target['taluka']}_{target['village']}_{ts}.png",
        )
        with open(final_path, "wb") as f:
            f.write(image_bytes)

    # Write summary JSON
    summary = {
        "success": True,
        "file": final_path,
        "file_size_bytes": os.path.getsize(final_path)
        if os.path.exists(final_path)
        else 0,
        "image_url": result.get("image_url"),
        "target": target,
        "completed_at": ts,
    }
    with open(final_path.replace(".png", "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    return final_path


# ═══════════════════════════════════════════════════════════════════════════
#  Main watchdog loop
# ═══════════════════════════════════════════════════════════════════════════


def main():
    deadline = datetime.now() + timedelta(hours=MAX_RUNTIME_HOURS)
    poll_count = 0
    scrape_count = 0
    started_at = datetime.now()

    logger.info("=" * 70)
    logger.info("PR CARD WATCHDOG STARTED")
    logger.info(f"  Poll interval  : {POLL_INTERVAL}s ({POLL_INTERVAL // 60} min)")
    logger.info(
        f"  Max runtime    : {MAX_RUNTIME_HOURS}h  (deadline: {deadline.strftime('%Y-%m-%d %H:%M')})"
    )
    logger.info(f"  Targets        : {len(TARGETS)}")
    logger.info(f"  CAPTCHA retries: {CAPTCHA_RETRIES}")
    logger.info(f"  Log            : {LOG_FILE}")
    logger.info(f"  Status file    : {STATUS_FILE}")
    logger.info("=" * 70)

    _write_status(
        {
            "phase": "polling",
            "started_at": started_at.isoformat(),
            "deadline": deadline.isoformat(),
            "poll_count": 0,
            "scrape_count": 0,
            "last_result": None,
        }
    )

    # ── Suppress SSL warnings from requests (gov site cert issues) ──────
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    while datetime.now() < deadline:
        poll_count += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[Poll #{poll_count}] {now_str} — probing site...")

        up = _site_is_up()
        logger.info(
            f"[Poll #{poll_count}] Site is {'UP' if up else 'DOWN (maintenance)'}"
        )

        _write_status(
            {
                "phase": "polling" if not up else "scraping",
                "started_at": started_at.isoformat(),
                "deadline": deadline.isoformat(),
                "poll_count": poll_count,
                "scrape_count": scrape_count,
                "site_up": up,
                "last_poll": now_str,
                "last_result": None,
            }
        )

        if up:
            # ── Site is up — attempt scrape across all targets ──────────
            logger.info("Site is UP — beginning scrape sequence")
            scrape_count += 1

            for t_idx, target in enumerate(TARGETS, 1):
                logger.info(
                    f"  Target {t_idx}/{len(TARGETS)}: "
                    f"{target['district']} / {target['taluka']} / "
                    f"{target['village']} [{target['record_of_right']}]"
                )

                result = _run_scrape(target)
                status = result.get("status", "unknown")
                logger.info(f"  Initial status: {status}")

                # CAPTCHA retry loop
                cap_tries = 0
                while status == "captcha_required" and cap_tries < CAPTCHA_RETRIES:
                    cap_tries += 1
                    cap_img = result.get("captcha_image")
                    if cap_img:
                        cap_path = os.path.join(
                            OUTPUT_DIR,
                            f"captcha_unsolved_{datetime.now().strftime('%H%M%S')}_try{cap_tries}.png",
                        )
                        with open(cap_path, "wb") as f:
                            f.write(cap_img)
                        logger.info(f"  Saved unsolved CAPTCHA to: {cap_path}")
                    logger.info(
                        f"  CAPTCHA retry {cap_tries}/{CAPTCHA_RETRIES} (fresh browser)..."
                    )
                    result = _run_scrape(target)
                    status = result.get("status", "unknown")
                    logger.info(f"  CAPTCHA retry {cap_tries} result: {status}")

                if status == "completed":
                    final_path = _persist_image(result, target)
                    file_size = (
                        os.path.getsize(final_path) if os.path.exists(final_path) else 0
                    )
                    image_url = result.get("image_url", "N/A")

                    logger.info("")
                    logger.info("=" * 70)
                    logger.info("  PR CARD IMAGE SUCCESSFULLY RETRIEVED!")
                    logger.info(f"  File      : {final_path}")
                    logger.info(f"  Size      : {file_size:,} bytes")
                    logger.info(f"  Image URL : {image_url}")
                    logger.info(
                        f"  Target    : {target['district']} / {target['taluka']} / {target['village']}"
                    )
                    logger.info(f"  Record    : {target['record_of_right']}")
                    logger.info("=" * 70)

                    _write_status(
                        {
                            "phase": "COMPLETED",
                            "started_at": started_at.isoformat(),
                            "completed_at": datetime.now().isoformat(),
                            "poll_count": poll_count,
                            "scrape_count": scrape_count,
                            "result": {
                                "file": final_path,
                                "file_size_bytes": file_size,
                                "image_url": image_url,
                                "target": target,
                            },
                        }
                    )
                    return True

                # Failed target — log and continue to next
                err = result.get("error", "")[:120]
                logger.warning(f"  Target {t_idx} exhausted ({status}): {err}")

            logger.warning(
                "All targets attempted without success — will retry on next poll"
            )

        # ── Wait before next poll ────────────────────────────────────────
        next_poll = datetime.now() + timedelta(seconds=POLL_INTERVAL)
        logger.info(
            f"Next poll at: {next_poll.strftime('%H:%M:%S')}  "
            f"(site is {'operational — retrying' if up else 'in maintenance'})"
        )
        time.sleep(POLL_INTERVAL)

    # ── Deadline exceeded ────────────────────────────────────────────────
    logger.error("WATCHDOG DEADLINE REACHED — exiting without a result.")
    _write_status(
        {
            "phase": "TIMEOUT",
            "started_at": started_at.isoformat(),
            "deadline": deadline.isoformat(),
            "poll_count": poll_count,
            "scrape_count": scrape_count,
        }
    )
    return False


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

