#!/usr/bin/env python3
"""
Diagnose what the Mahabhumi site actually looks like:
 - Takes a screenshot right after page load
 - Lists all select/input element IDs
 - Checks for overlays, iframes, alert dialogs
 - Saves everything to outputs/
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://bhulekh.mahabhumi.gov.in"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(0)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        },
    )

    try:
        print(f"Navigating to {BASE_URL} ...")
        driver.get(BASE_URL)

        # Wait for page ready
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print("readyState = complete")
        time.sleep(4)

        # Screenshot immediately after load
        ss_path = os.path.join(OUTPUT_DIR, "diag_01_initial_load.png")
        driver.get_screenshot_as_file(ss_path)
        print(f"Screenshot: {ss_path}")

        # Current URL
        print(f"Current URL: {driver.current_url}")
        print(f"Page title:  {driver.title}")

        # Check for any overlay
        overlay = driver.execute_script("""
            var ov = document.getElementById('customAlertOverlay');
            if (ov && ov.style.display !== 'none') {
                return {visible: true, text: (ov.innerText||'').substring(0,200)};
            }
            return {visible: false};
        """)
        print(f"Overlay: {overlay}")

        # Dismiss any overlay
        driver.execute_script("""
            if (typeof closeCustomAlert === 'function') closeCustomAlert();
            var ov = document.getElementById('customAlertOverlay');
            if (ov) ov.style.display = 'none';
        """)
        time.sleep(1)

        # Screenshot after overlay dismissed
        ss2 = os.path.join(OUTPUT_DIR, "diag_02_after_overlay.png")
        driver.get_screenshot_as_file(ss2)
        print(f"Screenshot after overlay: {ss2}")

        # List ALL select elements
        selects = driver.execute_script("""
            return Array.from(document.querySelectorAll('select')).map(s => ({
                id: s.id, name: s.name, optionCount: s.options.length,
                firstOption: s.options[0] ? s.options[0].text : '',
                display: window.getComputedStyle(s).display,
                visible: s.offsetParent !== null
            }));
        """)
        print(f"\nSELECT elements ({len(selects)}):")
        for s in selects:
            print(
                f"  id={s['id']!r:45} visible={s['visible']} opts={s['optionCount']} first={s['firstOption']!r}"
            )

        # List ALL input elements
        inputs = driver.execute_script("""
            return Array.from(document.querySelectorAll('input')).map(i => ({
                id: i.id, name: i.name, type: i.type,
                visible: i.offsetParent !== null
            }));
        """)
        print(f"\nINPUT elements ({len(inputs)}):")
        for inp in inputs:
            print(
                f"  id={inp['id']!r:45} type={inp['type']!r} visible={inp['visible']}"
            )

        # List ALL buttons
        buttons = driver.execute_script("""
            return Array.from(document.querySelectorAll('button, input[type=submit], input[type=button]')).map(b => ({
                id: b.id, text: (b.innerText||b.value||'').substring(0,40),
                visible: b.offsetParent !== null
            }));
        """)
        print(f"\nBUTTON elements ({len(buttons)}):")
        for b in buttons:
            print(f"  id={b['id']!r:45} text={b['text']!r}")

        # Check for iframes
        iframes = driver.execute_script("""
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                id: f.id, src: f.src, name: f.name
            }));
        """)
        print(f"\nIFRAME elements ({len(iframes)}):")
        for fr in iframes:
            print(f"  {fr}")

        # Check specific known element
        known_ids = [
            "ContentPlaceHolder1_ddlMainDist",
            "ddlMainDist",
            "ctl00_ContentPlaceHolder1_ddlMainDist",
        ]
        print("\nChecking known element IDs:")
        for eid in known_ids:
            exists = driver.execute_script(
                f"return document.getElementById('{eid}') !== null;"
            )
            print(f"  {eid}: {'FOUND' if exists else 'NOT FOUND'}")

        # Get the page body text (first 1000 chars)
        body_text = driver.execute_script(
            "return document.body.innerText.substring(0, 1000);"
        )
        print(f"\nPage body text (first 1000 chars):\n{body_text}")

        # Save all element IDs to JSON for full analysis
        all_ids = driver.execute_script("""
            return Array.from(document.querySelectorAll('[id]')).map(e => e.id).filter(Boolean);
        """)
        ids_path = os.path.join(OUTPUT_DIR, "diag_element_ids.json")
        with open(ids_path, "w") as f:
            json.dump(all_ids, f, indent=2)
        print(f"\nAll element IDs saved to: {ids_path}")

        # Try clicking around to find the form
        # Check if there's a link/button that leads to the property card form
        links = driver.execute_script("""
            return Array.from(document.querySelectorAll('a[href], button')).map(a => ({
                text: (a.innerText||a.textContent||'').trim().substring(0,60),
                href: a.href || ''
            })).filter(a => a.text.length > 0);
        """)
        print(f"\nLinks/buttons ({len(links)}):")
        for lnk in links[:30]:
            href_short = lnk["href"][:60]
            print(f"  text={lnk['text']!r:50} href={href_short!r}")

    finally:
        driver.quit()
        print("\nDone. Check outputs/ for screenshots.")


if __name__ == "__main__":
    main()
