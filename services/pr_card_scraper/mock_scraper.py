"""
Mock PR Card Scraper for testing when Mahabhumi website is inaccessible.
Returns sample PR card images for development and testing.
"""

import logging
import os
import asyncio
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
import io
import time

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


class MockMahabhumiScraper:
    """Mock scraper that generates sample PR card images."""

    BASE_URL = "https://bhulekh.mahabhumi.gov.in"

    def __init__(self, browser=None):
        # Ignore browser parameter for mock
        logger.info("Initialized Mock Mahabhumi Scraper")

    async def scrape_pr_card(
        self,
        district: str,
        taluka: str,
        village: str,
        survey_no: str,
        survey_no_part1: Optional[str] = None,
        mobile: str = "9876543210",
        property_uid: Optional[str] = None,
        language: str = "EN",
        record_of_right: str = "Property Card",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Mock scrape flow that generates a sample PR card image.
        """
        logger.info(f"Mock scraping PR Card for {district}, {taluka}, {village}")

        # Simulate processing delay
        await asyncio.sleep(2)

        # Generate a sample PR card image
        image_bytes = self._generate_sample_pr_card(
            district, taluka, village, survey_no, mobile
        )

        # Save image
        timestamp = int(time.time())
        output_path = os.path.join(OUTPUT_DIR, f"pr_card_mock_{timestamp}.png")

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"Generated mock PR Card image: {output_path}")

        return {
            "status": "completed",
            "image_bytes": image_bytes,
            "output_path": output_path,
            "image_url": f"mock://pr_card_{timestamp}.png",
            "message": "Generated mock PR Card (Mahabhumi website inaccessible)",
        }

    async def scrape_with_captcha(
        self,
        form_state: dict,
        captcha_value: str,
    ) -> dict:
        """Mock CAPTCHA resume - just calls the main scrape method."""
        logger.info("Mock CAPTCHA resume")
        return await self.scrape_pr_card(**form_state)

    def _generate_sample_pr_card(
        self, district: str, taluka: str, village: str, survey_no: str, mobile: str
    ) -> bytes:
        """Generate a sample PR card image with the provided details."""

        # Create a sample PR card-like image
        width, height = 800, 1000
        image = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(image)

        # Try to use a default font, fallback to default if not available
        try:
            # Try to load a font (this might fail on some systems)
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_medium = ImageFont.truetype("arial.ttf", 18)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except IOError:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw border
        draw.rectangle([10, 10, width - 10, height - 10], outline="black", width=2)

        # Title
        draw.text(
            (width // 2, 50),
            "PROPERTY CARD",
            fill="black",
            font=font_large,
            anchor="mm",
        )
        draw.text(
            (width // 2, 80),
            "(पी.पी. कार्ड)",
            fill="black",
            font=font_medium,
            anchor="mm",
        )

        # Details
        y_pos = 130
        line_height = 25

        details = [
            f"District: {district}",
            f"Taluka: {taluka}",
            f"Village: {village}",
            f"Survey No: {survey_no}",
            f"Mobile: {mobile}",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "NOTE: This is a mock PR Card generated for testing",
            "purposes when the Mahabhumi website is inaccessible.",
            "",
            "In production, this would connect to:",
            "https://bhulekh.mahabhumi.gov.in",
            "",
            "To fix connectivity:",
            "1. Check network/firewall settings",
            "2. Ensure VPN/proxy allows access to mahabhumi.gov.in",
            "3. Verify DNS resolution works",
        ]

        for detail in details:
            if detail == "":
                y_pos += line_height // 2
                continue
            draw.text((30, y_pos), detail, fill="black", font=font_small)
            y_pos += line_height

        # Add a sample watermark
        draw.text(
            (width // 2, height - 50),
            "SAMPLE - NOT FOR OFFICIAL USE",
            fill="red",
            font=font_medium,
            anchor="mm",
        )

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()

    async def start(self):
        """Mock start method for compatibility."""
        logger.info("Mock browser service started")
        return self

    async def stop(self):
        """Mock stop method for compatibility."""
        logger.info("Mock browser service stopped")


def create_mock_browser_service(headless: bool = False) -> MockMahabhumiScraper:
    """Create and return mock browser service."""
    return MockMahabhumiScraper()


# Export for compatibility
MahabhumiScraperSelenium = MockMahabhumiScraper
create_browser_service = create_mock_browser_service

