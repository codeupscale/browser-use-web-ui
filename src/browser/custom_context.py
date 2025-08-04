import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
from browser_use.browser.context import BrowserContextState

logger = logging.getLogger(__name__)

class CustomBrowserContext(BrowserContext):
    def __init__(
        self,
        browser: 'Browser',
        config: BrowserContextConfig | None = None,
        state: Optional[BrowserContextState] = None,
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config, state=state)
        self._playwright_context: Optional[PlaywrightBrowserContext] = None

    async def _setup_context(self) -> PlaywrightBrowserContext:
        """Set up the Playwright context with video recording enabled"""
        logger.info("\n[DEBUG] Creating new browser context...")
        
        # Create videos directory under src/outputdata
        # Paths for local development
        # video_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputdata", "videos")
        
        # Paths for Dockerized application
        video_dir = os.path.join("/app", "src", "outputdata", "videos")
        os.makedirs(video_dir, exist_ok=True)
        logger.info(f"[DEBUG] Video directory: {video_dir}")
        
        context = await self.browser.playwright_browser.new_context(
            record_video_dir=video_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        logger.info("[DEBUG] Context created with video recording settings")
        
        # Add page event handler
        async def handle_new_page(page):
            logger.info(f"[DEBUG] New page created: {page}")
            if hasattr(page, 'video'):
                logger.info(f"[DEBUG] New page has video attribute")
            else:
                logger.info(f"[DEBUG] New page has NO video attribute")
        
        context.on("page", handle_new_page)
        logger.info("[DEBUG] Page event handler added")
        
        return context

    async def setup(self):
        # This is the method that will be called from the browser_use_agent_tab
        self._playwright_context = await self._setup_context()

    async def _create_context(self, browser: PlaywrightBrowser) -> BrowserContext:
        """Create a new browser context with video recording enabled"""
        logger.info("\n[DEBUG] Creating new browser context...")
        context = await browser.new_context(
            # Paths for local development
            # record_video_dir="outputdata/videos",
            
            # Paths for Dockerized application
            record_video_dir="/app/src/outputdata/videos",
            record_video_size={"width": 1280, "height": 720}
        )
        logger.info("[DEBUG] Context created with video recording settings")
        
        # Add page event handler
        async def handle_new_page(page):
            logger.info(f"[DEBUG] New page created: {page}")
            if hasattr(page, 'video'):
                logger.info(f"[DEBUG] New page has video attribute")
            else:
                logger.info(f"[DEBUG] New page has NO video attribute")
        
        context.on("page", handle_new_page)
        logger.info("[DEBUG] Page event handler added")
        
        # Check initial pages
        for i, page in enumerate(context.pages):
            logger.info(f"[DEBUG] Initial page {i}: {page}")
            if hasattr(page, 'video'):
                logger.info(f"[DEBUG] Initial page {i} has video attribute")
            else:
                logger.info(f"[DEBUG] Initial page {i} has NO video attribute")
        
        return context

    async def stop_video_recording(self):
        """Stop video recording for all pages without closing the context"""
        if not self._playwright_context:
            return

        pages = self._playwright_context.pages
        logger.info(f"\n[DEBUG] Stopping video recording for {len(pages)} pages")
        
        for i, page in enumerate(pages):
            if hasattr(page, 'video'):
                try:
                    # Close the video artifact to stop recording
                    await page.video.delete()
                    logger.info(f"[DEBUG] Stopped video recording for page {i}")
                except Exception as e:
                    logger.error(f"[DEBUG] Error stopping video for page {i}: {e}")

    async def save_videos(self) -> List[str]:
        """Save video recordings without closing the context"""
        if not self._playwright_context:
            return []

        video_paths = []
        pages = self._playwright_context.pages
        logger.info(f"\n[DEBUG] Saving videos for {len(pages)} pages")
        
        for i, page in enumerate(pages):
            logger.info(f"[DEBUG] Checking page {i}: {page}")
            if hasattr(page, 'video'):
                logger.info(f"[DEBUG] Page {i} has video attribute")
                try:
                    video_path = await page.video.path()
                    logger.info(f"[DEBUG] Page {i} video path: {video_path}")
                    video_paths.append(video_path)
                    # Stop recording after saving
                    await page.video.delete()
                    logger.info(f"[DEBUG] Stopped recording for page {i}")
                except Exception as e:
                    logger.error(f"[DEBUG] Error handling video for page {i}: {e}")
            else:
                logger.info(f"[DEBUG] Page {i} has NO video attribute")
        
        return video_paths

    async def close(self):
        """Close the context and save the video recording(s)"""
        logger.info("\n[DEBUG] ===== CLOSE METHOD CALLED =====")
        if self._playwright_context:
            # Save any remaining videos
            video_paths = await self.save_videos()
            
            # Close the context
            await self._playwright_context.close()
            self._playwright_context = None
            
            return video_paths
        return None
