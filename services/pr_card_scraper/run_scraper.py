#!/usr/bin/env python3
"""
Standalone PR Card Scraper — Updated to use Playwright and Modular architecture.
"""

import argparse
import asyncio
import json
import logging
import os
import sys

# ── make service modules importable ──────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _WORKSPACE_ROOT)
sys.path.insert(0, _HERE)

import contextlib
from dotenv import load_dotenv

dotenv_path = os.path.join(_WORKSPACE_ROOT, ".env")
load_dotenv(dotenv_path)

from services.browser import BaseBrowser, MahabhumiScraper

# ═════════════════════════════════════════════════════════════════════════════
#  SCRAPE TARGETS
# ═════════════════════════════════════════════════════════════════════════════
TARGETS = [
    # FP 63, TPS VILE PARLE No.VI, Vile Parle West (CTS 909)
    {
        "district": "mumbai suburban",
        "taluka": "vile parle",  # नगर भूमापन अधिकारी,विलेपार्ले
        "village": "vile parle west",
        "survey_no": "909",  # CTS 909 = FP 63, TPS VILE PARLE No.VI
        "survey_no_part1": None,
        "mobile": "9999999999",
    },
]

OUTPUT_DIR = os.path.join(_HERE, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_scraper")


async def run_one_target(target: dict, headless: bool) -> dict:
    browser = BaseBrowser(headless=headless)
    try:
        await browser.start()
        scraper = MahabhumiScraper(browser)

        async def on_captcha(img_bytes: bytes) -> str:
            """Prompt user to solve CAPTCHA when auto-solver fails."""
            import subprocess

            captcha_path = os.path.join(OUTPUT_DIR, "captcha_manual.png")
            with open(captcha_path, "wb") as f:
                f.write(img_bytes)
            # Open the image automatically
            with contextlib.suppress(Exception):
                subprocess.Popen(["explorer", captcha_path])
            
            # Wait for captcha_answer.txt file to be created (120s timeout)
            answer_file = os.path.join(OUTPUT_DIR, "captcha_answer.txt")
            if os.path.exists(answer_file):
                os.remove(answer_file)
            
            print(f"\n=== MANUAL CAPTCHA REQUIRED ===")
            print(f"CAPTCHA image saved to: {captcha_path}")
            print(f"Please create file: {answer_file}")
            print(f"With the CAPTCHA text as content. Waiting 120 seconds...\n")
            
            for _ in range(120):
                await asyncio.sleep(1)
                if os.path.exists(answer_file):
                    with open(answer_file) as f:
                        answer = f.read().strip()
                    os.remove(answer_file)
                    print(f"CAPTCHA answer received: {answer}")
                    return answer
            
            print("Timeout waiting for CAPTCHA answer")
            return None

        return await scraper.scrape_pr_card(on_captcha=on_captcha, **target)
    except Exception as exc:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return {"status": "failed", "error": str(exc)}
    finally:
        await browser.stop()


async def main(headless: bool):
    logger.info("=" * 70)
    logger.info("PR CARD SCRAPER — PLAYWRIGHT STANDALONE")
    logger.info("=" * 70)

    for idx, target in enumerate(TARGETS, 1):
        logger.info(f"\n── Target {idx}/{len(TARGETS)}: {target['district']} ──")
        result = await run_one_target(target, headless)

        if result.get("status") == "completed":
            logger.info("SUCCESS!")
            logger.info(f"Output: {result.get('output_path')}")
            logger.info(f"Extracted Data: {json.dumps(result.get('extracted_data'), indent=2)}")
        else:
            logger.error(f"FAILED: {result.get('error')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    args = parser.parse_args()

    asyncio.run(main(headless=not args.visible))
