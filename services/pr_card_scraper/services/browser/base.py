import logging

from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)


class BaseBrowser:
    """Base class for Playwright browser management."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.stealth = Stealth()

    async def start(self):
        """Start Playwright and launch browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        logger.info("Playwright browser started")

    async def stop(self):
        """Stop Playwright and close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Playwright browser stopped")

    async def new_page(self) -> Page:
        """Create a new page with stealth applied."""
        page = await self.context.new_page()
        await self.stealth.apply_stealth_async(page)

        # Block unnecessary resources to speed up loading
        await page.route("**/*", self._resource_filter)

        return page

    async def _resource_filter(self, route):
        """Filter out unnecessary resources like fonts and analytics."""
        # We need images for CAPTCHA and the final result, so we'll be selective
        if route.request.resource_type in ["font", "media", "ping"]:
            await route.abort()
        elif "google-analytics" in route.request.url or "googletagmanager" in route.request.url:
            await route.abort()
        else:
            await route.continue_()
