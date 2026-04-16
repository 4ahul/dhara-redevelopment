#!/usr/bin/env python3
"""
Quick Chrome-based site probe:
 - Opens the site with a real browser
 - Dismisses any overlay
 - Checks if the form dropdown exists
 - Takes a screenshot
 - Reports whether the form is accessible
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://bhulekh.mahabhumi.gov.in"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def probe():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(0)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        },
    )

    result = {"site_accessible": False, "form_visible": False, "status_detail": ""}

    try:
        print(f"Loading {BASE_URL} ...")
        driver.get(BASE_URL)

        # Wait up to 40s for page ready
        try:
            WebDriverWait(driver, 40).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass

        time.sleep(3)

        title = driver.title
        url = driver.current_url
        print(f"Title: {title}")
        print(f"URL:   {url}")

        # Screenshot
        ss = os.path.join(OUTPUT_DIR, "probe_screenshot.png")
        driver.get_screenshot_as_file(ss)
        print(f"Screenshot: {ss}")

        # Dismiss overlay if present
        driver.execute_script("""
            if (typeof closeCustomAlert === 'function') closeCustomAlert();
            var ov = document.getElementById('customAlertOverlay');
            if (ov) ov.style.display = 'none';
        """)
        time.sleep(1)

        # Check for district dropdown
        dist_el = driver.execute_script(
            "return document.getElementById('ContentPlaceHolder1_ddlMainDist');"
        )
        form_el = driver.execute_script(
            "return document.querySelectorAll('select, input[type=text]').length;"
        )

        is_error = "Runtime Error" in title or "Server Error" in driver.title
        form_present = dist_el is not None or (form_el and form_el > 2)

        result["site_accessible"] = not is_error
        result["form_visible"] = bool(form_present)
        result["status_detail"] = (
            f"title={title!r} forms={form_el} dist_dropdown={'found' if dist_el else 'missing'}"
        )

        print(f"\nSite accessible : {result['site_accessible']}")
        print(f"Form visible    : {result['form_visible']}")
        print(f"Detail          : {result['status_detail']}")

        # Take another screenshot after overlay dismissed
        ss2 = os.path.join(OUTPUT_DIR, "probe_after_overlay.png")
        driver.get_screenshot_as_file(ss2)
        print(f"Post-overlay screenshot: {ss2}")

        # List all select elements IDs
        selects = driver.execute_script(
            "return Array.from(document.querySelectorAll('select')).map(s => s.id);"
        )
        print(f"Select IDs: {selects}")

    finally:
        driver.quit()

    return result


if __name__ == "__main__":
    r = probe()
    print(
        f"\nFINAL: {'FORM IS ACCESSIBLE - READY TO SCRAPE' if r['form_visible'] else 'SITE IS DOWN'}"
    )
    sys.exit(0 if r["form_visible"] else 1)
