import asyncio
import os
import sys
import logging

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

out_dir = os.path.join(_HERE, "outputs")
os.makedirs(out_dir, exist_ok=True)
log_path = os.path.join(out_dir, "test_log6.txt")

logging.basicConfig(
    filename=log_path,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from services.browser import BaseBrowser
from services.browser.mahabhumi import MahabhumiFormHandler
from services.browser.extractor import ImageExtractor


async def run():
    logging.info("Starting browser...")
    browser = BaseBrowser(headless=True)
    await browser.start()
    page = await browser.new_page()

    form_handler = MahabhumiFormHandler(page)
    extractor = ImageExtractor(page)

    target = dict(
        district="pune",
        taluka="Pune City",
        village="Aundh",
        survey_no="1",
        survey_no_part1="1",
        mobile="9999999999",
        language="EN",
        record_of_right="Property Card",
        know_property_uid=False,
    )

    try:
        logging.info("Navigating and filling form...")
        await form_handler.navigate_to_base()
        await form_handler.fill_form(**target)

        captcha_path = os.path.join(out_dir, "captcha6.png")
        answer_path = os.path.join(out_dir, "answer6.txt")
        final_path = os.path.join(out_dir, "final_pr_card6.png")

        if os.path.exists(answer_path):
            os.remove(answer_path)

        captcha_bytes = await form_handler.get_captcha_image()
        with open(captcha_path, "wb") as f:
            f.write(captcha_bytes)

        logging.info(f"CAPTCHA saved to {captcha_path}. Waiting for {answer_path}...")

        # Wait for answer
        answer = None
        for i in range(300):  # wait up to 300 seconds
            if os.path.exists(answer_path):
                with open(answer_path, "r") as f:
                    answer = f.read().strip()
                if answer:
                    break
            await asyncio.sleep(1)

        if not answer:
            logging.error("Timed out waiting for CAPTCHA answer.")
            return

        logging.info(f"Got CAPTCHA answer: {answer}. Submitting...")
        extractor.clear()  # Clear previous images!
        await form_handler.submit_form(answer)

        logging.info("Waiting for result page...")
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            logging.warning(f"Wait for load state timeout: {e}")

        await asyncio.sleep(5)

        # Take a screenshot to see what happened after submit
        await page.screenshot(
            path=os.path.join(out_dir, "after_submit6.png"), full_page=True
        )
        logging.info("Saved after_submit6.png")

        logging.info("Extracting image...")
        img_bytes, img_url = await extractor.get_best_image(timeout=20)

        if img_bytes:
            with open(final_path, "wb") as f:
                f.write(img_bytes)
            logging.info(f"SUCCESS: PR Card saved to {final_path}")
            logging.info(f"Image URL: {img_url}")
        else:
            logging.error("FAILED to extract image.")
            await extractor.screenshot_fallback(
                final_path.replace(".png", "_fallback.png")
            )

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(run())
