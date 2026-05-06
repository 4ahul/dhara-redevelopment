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
sys.path.insert(0, _HERE)

import contextlib

from services.pr_card_scraper.services.browser import BaseBrowser, MahabhumiScraper

# ═════════════════════════════════════════════════════════════════════════════
#  SCRAPE TARGETS
# ═════════════════════════════════════════════════════════════════════════════
TARGETS = [
    # Narhe is in Haveli taluka (न-हे visible in dropdown, CTS survey type)
    {
        "district": "pune",
        "taluka": "Haveli",
        "village": "Narhe",
        "survey_no": "1",
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
            import sys

            captcha_path = os.path.join(OUTPUT_DIR, "captcha_manual.png")
            with open(captcha_path, "wb") as f:
                f.write(img_bytes)
            # Open the image automatically
            with contextlib.suppress(Exception):
                subprocess.Popen(["explorer", captcha_path])
            if not sys.stdin.isatty():
                # Non-interactive: poll for a captcha_answer.txt file (30s timeout)
                answer_file = os.path.join(OUTPUT_DIR, "captcha_answer.txt")
                if os.path.exists(answer_file):
                    os.remove(answer_file)
                for _ in range(120):
                    await asyncio.sleep(1)
                    if os.path.exists(answer_file):
                        with open(answer_file) as f:
                            answer = f.read().strip()
                        os.remove(answer_file)
                        return answer
                return None
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, input)
            return answer.strip()

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
