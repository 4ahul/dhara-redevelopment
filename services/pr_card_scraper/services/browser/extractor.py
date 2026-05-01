import asyncio
import base64
import logging
import time

from playwright.async_api import Page, Response

logger = logging.getLogger(__name__)

# URL fragments that identify the PR card image endpoint on Bhulekh
_PR_CARD_URL_KEYWORDS = [
    "showimage",
    "getimage",
    "propertycard",
    "prcard",
    "pr_card",
    "viewimage",
    "viewpc",
    "showpc",
    "imgpc",
]

_EXCLUDE_KEYWORDS = [
    "logo",
    "header",
    "footer",
    "icon",
    "banner",
    "loading",
    "captcha",
    "button",
    "div1_map",
    "cersai",
    "mcgm",
    "globalsign",
    "siteseal",
    "/images/",
    "/image/",
]


class ImageExtractor:
    """
    Extracts the PR Card image from Bhulekh using a strict priority:
      1. Network response interception (captures bytes on the wire)
      2. DOM: read #ContentPlaceHolder1_ImgPC.src (3 retries, relative→absolute)
      3. page.request.get(src) session-aware download (cookies included)
      4. Screenshot — absolute last resort only
    """

    def __init__(self, page: Page):
        self.page = page
        self._pr_card_responses: list[dict] = []  # high-confidence PR card captures
        self._other_responses: list[dict] = []  # lower-confidence captures
        self._active = False  # only capture after form submit
        self.page.on("response", self._handle_response)

    def activate(self):
        """Call this just before/after CAPTCHA submit to start intercepting responses."""
        self._pr_card_responses.clear()
        self._other_responses.clear()
        self._active = True
        logger.debug("ImageExtractor: response interception activated")

    def clear(self):
        self._pr_card_responses.clear()
        self._other_responses.clear()
        self._active = False

    async def _handle_response(self, response: Response):
        """Intercept network responses — only after activate() is called."""
        if not self._active:
            return

        url = response.url
        url_lower = url.lower()
        content_type = response.headers.get("content-type", "").lower()

        # Must be an image
        if "image" not in content_type:
            return
        # Skip GIFs (site decorations)
        if url_lower.endswith(".gif"):
            return
        # Skip explicitly excluded patterns
        if any(kw in url_lower for kw in _EXCLUDE_KEYWORDS):
            return

        is_pr_card = any(kw in url_lower for kw in _PR_CARD_URL_KEYWORDS)

        try:
            body = await response.body()
        except Exception:
            return

        # Require minimum size: PR cards are typically > 50 KB
        if len(body) < 50_000:
            return

        entry = {"url": url, "body": body, "size": len(body)}

        if is_pr_card:
            logger.info(f"[Intercepted] PR card image via network: {url} ({len(body):,} bytes)")
            self._pr_card_responses.append(entry)
        else:
            logger.info(
                f"[Intercepted] Large image via network (candidate): {url} ({len(body):,} bytes)"
            )
            self._other_responses.append(entry)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def wait_for_pr_card_image(self, timeout: int = 45) -> tuple[bytes | None, str | None]:
        """
        Primary extraction method. Priority:
          A. DOM #ContentPlaceHolder1_ImgPC.src → page.request.get() (3 retries)
          B. Network interception cache (high-confidence PR card URL)
          C. Network interception cache (any large image)
        Returns (bytes, url) or (None, None).
        """
        end_time = time.time() + timeout
        attempt = 0

        while time.time() < end_time:
            attempt += 1

            # ── A: DOM src approach ──────────────────────────────────────────
            result = await self._try_dom_img_src()
            if result:
                return result

            # ── B: High-confidence network capture ───────────────────────────
            if self._pr_card_responses:
                best = max(self._pr_card_responses, key=lambda x: x["size"])
                logger.info(
                    f"Using intercepted PR card image: {best['url']} ({best['size']:,} bytes)"
                )
                return best["body"], best["url"]

            # ── C: Any large network capture ─────────────────────────────────
            if self._other_responses and attempt >= 3:
                best = max(self._other_responses, key=lambda x: x["size"])
                logger.info(
                    f"Using best candidate image from network: {best['url']} ({best['size']:,} bytes)"
                )
                return best["body"], best["url"]

            remaining = end_time - time.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(2, remaining))

        logger.warning("wait_for_pr_card_image: timed out — no PR card image found")
        return None, None

    async def get_best_image(self, timeout: int = 20) -> tuple[bytes | None, str | None]:
        """
        Fallback polling that tries DOM + network captures then generic DOM scan.
        Called when wait_for_pr_card_image fails.
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            # Try DOM img src first
            result = await self._try_dom_img_src()
            if result:
                return result

            # High-confidence network captures
            if self._pr_card_responses:
                best = max(self._pr_card_responses, key=lambda x: x["size"])
                return best["body"], best["url"]

            # Generic DOM scan (all frames)
            result = await self._generic_dom_scan()
            if result:
                return result

            await asyncio.sleep(2)

        # Last chance: any large network capture
        all_candidates = self._pr_card_responses + self._other_responses
        if all_candidates:
            best = max(all_candidates, key=lambda x: x["size"])
            logger.warning(
                f"Timeout — returning best available: {best['url']} ({best['size']:,} bytes)"
            )
            return best["body"], best["url"]

        return None, None

    async def screenshot_fallback(self, path: str):
        """
        Absolute last resort — only called when ALL other strategies fail.
        Tries to capture just the result panel, falls back to full page.
        """
        logger.warning(f"screenshot_fallback: saving to {path}")
        result_selectors = [
            "#ContentPlaceHolder1_pnlPrint",
            "#ContentPlaceHolder1_divPrint",
            "#ContentPlaceHolder1_pnlResult",
        ]
        for sel in result_selectors:
            try:
                loc = self.page.locator(sel)
                if await loc.is_visible(timeout=2000):
                    await loc.screenshot(path=path)
                    logger.info(f"screenshot_fallback: captured {sel}")
                    return
            except Exception:
                continue
        try:
            await self.page.screenshot(path=path, full_page=True)
        except Exception as e:
            logger.error(f"screenshot_fallback failed entirely: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _try_dom_img_src(self) -> tuple[bytes, str] | None:
        """
        Read #ContentPlaceHolder1_ImgPC.src from the page (all frames).
        Retries 3 times if src is empty. Converts relative URLs to absolute.
        Downloads via page.request.get() so cookies are included.
        """
        pages_to_check = [self.page] + list(self.page.frames)

        for frame in pages_to_check:
            for _attempt in range(3):
                try:
                    src = await frame.evaluate("""
                        () => {
                            const el = document.getElementById('ContentPlaceHolder1_ImgPC');
                            if (!el) return null;
                            let s = el.src || '';
                            // Convert relative → absolute
                            if (s && !s.startsWith('http') && !s.startsWith('data:')) {
                                s = new URL(s, window.location.href).href;
                            }
                            return (s && s.length > 20) ? s : null;
                        }
                    """)

                    if not src:
                        await asyncio.sleep(1)
                        continue

                    logger.info(f"Found #ContentPlaceHolder1_ImgPC.src: {src[:120]}")

                    # Handle base64 data URI directly
                    if src.startswith("data:image"):
                        _, b64data = src.split(",", 1)
                        img_bytes = base64.b64decode(b64data)
                        if len(img_bytes) > 5000:
                            logger.info(f"Decoded base64 PR card image ({len(img_bytes):,} bytes)")
                            return img_bytes, "data:image/jpeg;base64"
                        await asyncio.sleep(1)
                        continue

                    # HTTP URL — download with session (cookies included)
                    if src.startswith("http"):
                        img_bytes = await self._download_with_retry(src)
                        if img_bytes and len(img_bytes) > 5000:
                            logger.info(
                                f"Downloaded PR card image ({len(img_bytes):,} bytes) from {src}"
                            )
                            return img_bytes, src

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.debug(f"_try_dom_img_src frame attempt failed: {e}")
                    await asyncio.sleep(1)

        return None

    async def _download_with_retry(self, url: str, retries: int = 3) -> bytes | None:
        """Download URL via Playwright session (cookies), with retries."""
        for attempt in range(1, retries + 1):
            try:
                resp = await self.page.request.get(url)
                if resp.ok:
                    body = await resp.body()
                    if body:
                        return body
                    logger.warning(f"Download attempt {attempt}: empty body from {url}")
                else:
                    logger.warning(f"Download attempt {attempt}: HTTP {resp.status} from {url}")
            except Exception as e:
                logger.warning(f"Download attempt {attempt} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(2 * attempt)
        return None

    async def _generic_dom_scan(self) -> tuple[bytes, str] | None:
        """
        Scan all frames for any large image, prioritising PR card URL keywords.
        Used as a last-chance fallback when the specific element isn't found.
        """
        for frame in self.page.frames:
            try:
                img_src = await frame.evaluate("""
                    () => {
                        const prImg = document.getElementById('ContentPlaceHolder1_ImgPC');
                        if (prImg && prImg.src && prImg.src.length > 20) {
                            let s = prImg.src;
                            if (!s.startsWith('http') && !s.startsWith('data:')) {
                                s = new URL(s, window.location.href).href;
                            }
                            return s;
                        }

                        const priorityKw = ['showimage','getimage','propertycard','prcard','pr_card','viewimage','viewpc','showpc'];
                        const excludeKw  = ['logo','header','footer','icon','banner','captcha','.gif','div1_map','globalsign','siteseal','/images/','/image/'];

                        let best = null, maxScore = -1;
                        for (const img of document.querySelectorAll('img')) {
                            const src = img.src || '';
                            const sl = src.toLowerCase();
                            if (excludeKw.some(k => sl.includes(k))) continue;
                            if (!src.startsWith('http') && !src.startsWith('data:image')) continue;
                            let score = (img.naturalWidth || 0) * (img.naturalHeight || 0);
                            if (priorityKw.some(k => sl.includes(k))) score += 5_000_000;
                            if (score > maxScore) { maxScore = score; best = src; }
                        }
                        return best;
                    }
                """)

                if not img_src:
                    continue

                if img_src.startswith("data:image"):
                    _, b64data = img_src.split(",", 1)
                    img_bytes = base64.b64decode(b64data)
                    if len(img_bytes) > 5000:
                        return img_bytes, "data:image/jpeg;base64"
                    continue

                if img_src.startswith("http"):
                    img_bytes = await self._download_with_retry(img_src)
                    if img_bytes and len(img_bytes) > 5000:
                        return img_bytes, img_src

            except Exception:
                continue

        return None
