"""
Playwright-based scraper for Twitch channel panels.

Twitch panels are NOT available via Helix API and require browser automation.
This module provides async/sync scraping with singleton browser management.
"""

import asyncio
import logging
from typing import Any

import nest_asyncio
from playwright.async_api import Browser, async_playwright

# Allow nested event loops (needed when MCP server is already running an event loop)
nest_asyncio.apply()

logger = logging.getLogger(__name__)

# Singleton browser instance
_browser: Browser | None = None
_playwright = None


async def _get_browser() -> Browser:
    """Get or create singleton browser instance."""
    global _browser, _playwright

    if _browser is not None:
        return _browser

    logger.info("Starting Playwright browser (chromium, headless)")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    return _browser


async def _close_browser():
    """Close singleton browser instance."""
    global _browser, _playwright

    if _browser:
        await _browser.close()
        _browser = None

    if _playwright:
        await _playwright.stop()
        _playwright = None

    logger.info("Closed Playwright browser")


class PanelScraper:
    """Scraper for Twitch channel panels using Playwright."""

    async def scrape_panels_async(
        self, username: str, timeout_ms: int = 10000
    ) -> list[dict[str, Any]]:
        """
        Scrape panels from a Twitch channel (async).

        Args:
            username: Twitch username
            timeout_ms: Page load timeout in milliseconds

        Returns:
            List of panel dicts with title, description, image_url, link_url.
            Returns [] on error (graceful degradation).
        """
        try:
            browser = await _get_browser()
        except Exception as e:
            logger.warning(f"Failed to get browser for {username}: {e}")
            return []

        page = await browser.new_page()

        try:
            url = f"https://www.twitch.tv/{username}/about"
            logger.debug(f"Scraping panels from {url}")

            # Load page with timeout
            await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

            # Wait for dynamic content to load
            await asyncio.sleep(3)

            # Try to close any modals that might be blocking
            try:
                close_button = await page.query_selector('[aria-label="Close"]')
                if close_button:
                    await close_button.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Wait for panel elements (5s timeout)
            try:
                await page.wait_for_selector(
                    '[data-a-target="about-panel"], [class*="default-panel"]', timeout=5000
                )
            except Exception as e:
                logger.warning(f"Panels not found for {username}: {e}")
                return []

            # Extract panel data - both About panel and custom panels
            panels = []

            # Get About panel (bio section)
            about_panels = await page.query_selector_all('[data-a-target="about-panel"]')

            # Get custom panels (Game Grimoire, The Rig, etc.)
            custom_panels = await page.query_selector_all('[class*="default-panel"]')

            # Combine all panels
            panel_elements = about_panels + custom_panels

            for elem in panel_elements:
                try:
                    # Extract title (h2, h3, or h4 for custom panels)
                    title_elem = await elem.query_selector("h2, h3, h4")
                    title = await title_elem.inner_text() if title_elem else ""

                    # Extract description (p, div with description class, or panel-description class)
                    desc_elem = await elem.query_selector('p, div[class*="description"], .panel-description')
                    description = await desc_elem.inner_text() if desc_elem else ""

                    # Extract image URL
                    img_elem = await elem.query_selector("img")
                    image_url = await img_elem.get_attribute("src") if img_elem else ""

                    # Extract link URL
                    link_elem = await elem.query_selector("a")
                    link_url = await link_elem.get_attribute("href") if link_elem else ""

                    # Only add panel if it has at least title or description
                    if title or description:
                        panels.append(
                            {
                                "title": title.strip(),
                                "description": description.strip(),
                                "image_url": image_url,
                                "link_url": link_url,
                            }
                        )

                except Exception as e:
                    logger.debug(f"Error parsing panel element: {e}")
                    continue

            logger.info(f"Scraped {len(panels)} panels for {username}")
            return panels

        except Exception as e:
            logger.warning(f"Panel scraping failed for {username}: {e}")
            return []

        finally:
            await page.close()

    def scrape_panels_sync(self, username: str, timeout_seconds: int = 20) -> list[dict[str, Any]]:
        """
        Scrape panels from a Twitch channel (sync wrapper).

        This is the sync wrapper for MCP tool compatibility.

        Args:
            username: Twitch username
            timeout_seconds: Overall timeout for the scrape operation (default: 20s)

        Returns:
            List of panel dicts. Returns [] on error.
        """
        async def _scrape_with_timeout():
            return await asyncio.wait_for(
                self.scrape_panels_async(username),
                timeout=timeout_seconds
            )

        try:
            # Run async scraping in new event loop with overall timeout
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_scrape_with_timeout())
            finally:
                loop.close()
        except asyncio.TimeoutError:
            logger.warning(f"Panel scraping timed out for {username} after {timeout_seconds}s")
            return []
        except Exception as e:
            logger.error(f"Sync scraping failed for {username}: {e}")
            return []


# Singleton instance
_panel_scraper: PanelScraper | None = None


def get_panel_scraper() -> PanelScraper:
    """Get singleton PanelScraper instance."""
    global _panel_scraper

    if _panel_scraper is None:
        _panel_scraper = PanelScraper()

    return _panel_scraper


async def cleanup_panel_scraper():
    """Cleanup browser resources on shutdown."""
    await _close_browser()
