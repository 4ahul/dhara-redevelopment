import asyncio
import os
import sys
import logging
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from services.browser import BaseBrowser
from services.browser.mahabhumi import MahabhumiFormHandler
from services.browser.extractor import ImageExtractor
from services.captcha_solver import CaptchaSolver


async def run():
    out_dir = os.path.join(_HERE, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "interactive_test_run.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )
    logger = logging.getLogger("interactive_test")
    logger.info("Starting automated test with ddddocr...")
    browser = BaseBrowser(headless=True)
    await browser.start()
    page = await browser.new_page()

    form_handler = MahabhumiFormHandler(page)
    extractor = ImageExtractor(page)
    captcha_solver = CaptchaSolver()

    target = dict(
        district="Mumbai Suburban",
        taluka="Andheri",
        village="Bandra",
        survey_no="100",
        survey_no_part1="1",
        mobile="9820098200",
        language="EN",
        record_of_right="Property Card",
        property_uid_known=False,
    )

    try:
        logger.info("Navigating to base...")
        await form_handler.navigate_to_base()
        logger.info("Filling form...")
        await form_handler.fill_form(**target)

        out_dir = os.path.join(_HERE, "outputs")
        os.makedirs(out_dir, exist_ok=True)

        captcha_path = os.path.join(out_dir, "captcha_image.png")
        timestamp = int(time.time())
        final_path = os.path.join(out_dir, f"final_pr_card_{timestamp}.png")

        logger.info("Getting CAPTCHA image...")
        captcha_bytes = await form_handler.get_captcha_image()
        logger.info(f"CAPTCHA bytes received: {len(captcha_bytes)}")
        with open(captcha_path, "wb") as f:
            f.write(captcha_bytes)
        logger.info(f"CAPTCHA saved to {captcha_path}")

        logger.info("Solving CAPTCHA with ddddocr...")
        candidates = captcha_solver.solve(captcha_bytes)
        if not candidates:
            logger.error("Failed to solve CAPTCHA.")
            return

        answer = candidates[0]
        logger.info(f"Got CAPTCHA answer: {answer}. Submitting...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await form_handler.submit_form(answer)
                break
            except Exception as e:
                logger.warning(f"Submission failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info("Retrying with new CAPTCHA...")
                    captcha_bytes = await form_handler.get_captcha_image()
                    candidates = captcha_solver.solve(captcha_bytes)
                    if not candidates:
                        logger.error("Failed to solve new CAPTCHA.")
                        return
                    answer = candidates[0]
                    logger.info(f"Trying new answer: {answer}")
                else:
                    logger.error("Max CAPTCHA retries reached.")
                    return

        logger.info("Waiting for result page...")

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(10)

        logger.info("Extracting image...")
        img_bytes, img_url = await extractor.get_best_image(timeout=30)

        if img_bytes:
            with open(final_path, "wb") as f:
                f.write(img_bytes)
            print(f"SUCCESS: PR Card saved to {final_path}")
            print(f"Image URL: {img_url}")
        else:
            print("FAILED to extract image.")
            await extractor.screenshot_fallback(
                final_path.replace(".png", "_fallback.png")
            )

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(run())
