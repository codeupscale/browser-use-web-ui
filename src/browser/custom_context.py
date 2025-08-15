import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional, List, Set
from urllib.parse import urlparse

from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
from browser_use.browser.context import BrowserContextState
from src.outputdata.output_data import merge_videos_in_order

logger = logging.getLogger(__name__)

class CustomBrowserContext(BrowserContext):
    def __init__(self, browser: 'Browser',
                 config: BrowserContextConfig | None = None,
                 state: Optional[BrowserContextState] = None):
        super().__init__(browser=browser, config=config, state=state)
        self._playwright_context: Optional[PlaywrightBrowserContext] = None
        self._playwright_contexts: List[PlaywrightBrowserContext] = []
        self._handled_pages: Set = set()
        self._base_video_dir = os.path.join("/app", "src", "outputdata", "videos")

        self.tab_counter = 0
        self.tab_records: dict = {}
        self.context_records: dict = {}
        self._claimed_videos: Set[str] = set()
        self._closed_tabs: List[dict] = []
        self._base_dir_cleaned = False
        self._merged_video_path: Optional[str] = None

    async def setup(self):
        logger.info("[DEBUG] setup() no-op; handled in _create_context")
        return None

    def _get_all_contexts(self) -> List[PlaywrightBrowserContext]:
        contexts = list(self._playwright_contexts)
        if self._playwright_context and self._playwright_context not in contexts:
            contexts.append(self._playwright_context)
        return contexts

    async def _create_context(self, browser: PlaywrightBrowser) -> BrowserContext:
        logger.info("\n[DEBUG] Creating new browser context...")
        if not self._base_dir_cleaned:
            shutil.rmtree(self._base_video_dir, ignore_errors=True)
            self._base_dir_cleaned = True
        os.makedirs(self._base_video_dir, exist_ok=True)

        context = await browser.new_context(
            record_video_dir=self._base_video_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        logger.info("[DEBUG] Context created with recording")
        self._playwright_contexts.append(context)

        async def handle_new_page(page):
            self.tab_counter += 1
            seq = self.tab_counter
            url_now = page.url or "about:blank"
            url_slug = self._url_to_slug(url_now)
            self.tab_records[page] = {
                "seq": seq, "url": url_now,
                "dir": os.path.join(self._base_video_dir, f"tab_{seq:03d}_{url_slug}")
            }

            page.on("framenavigated", lambda _: self.tab_records[page].update(url=page.url))

            async def on_close():
                info = self.tab_records.get(page, {})
                seq_c = info.get("seq", seq)
                url_c = info.get("url", url_now)
                url_slug_c = self._url_to_slug(url_c)
                dir_c = info.get("dir") or os.path.join(self._base_video_dir, f"tab_{seq_c:03d}_{url_slug_c}")
                os.makedirs(dir_c, exist_ok=True)

                try:
                    original_path = await page.video.path() if hasattr(page, "video") else None
                except Exception:
                    original_path = None

                moved = False
                if original_path and os.path.exists(original_path) and original_path not in self._claimed_videos:
                    new_path = os.path.join(dir_c, f"tab_{seq_c:03d}_{url_slug_c}.webm")
                    try:
                        if original_path != new_path:
                            os.rename(original_path, new_path)
                        self._claimed_videos.add(new_path)
                        moved = True
                    except Exception:
                        pass

                if not moved:
                    self._closed_tabs.append({"seq": seq_c, "url": url_c, "dir": dir_c})

            page.on("close", on_close)
            logger.info(f"[TAB {seq:03d}] Tracking page: {url_now}")

        context.on("page", handle_new_page)

        for existing_page in list(context.pages):
            try:
                await handle_new_page(existing_page)
            except Exception as e:
                logger.warning(f"[DEBUG] Failed to process existing page: {e}")

        return context

    async def stop_video_recording(self):
        logger.info('Stop video recording for all contexts')
        for ctx in self._get_all_contexts():
            for i, page in enumerate(list(ctx.pages)):
                if hasattr(page, 'video'):
                    try:
                        await page.close()
                        logger.info(f"[DEBUG] Closed page {i} to finalize video")
                    except Exception as e:
                        logger.error(f"[DEBUG] Error closing page {i}: {e}")

    async def save_videos(self) -> List[str]:
        video_paths: List[str] = []

        for ctx in self._get_all_contexts():
            try:
                pages = list(ctx.pages)
            except Exception:
                continue

            for page in pages:
                info = self.tab_records.get(page, {})
                seq = info.get("seq", 0)
                url = info.get("url", "unknown")
                dir_hint = info.get("dir")
                url_slug = self._url_to_slug(url)

                try:
                    await page.close()
                except Exception:
                    pass

                try:
                    original_path = await page.video.path() if hasattr(page, "video") else None
                except Exception:
                    original_path = None

                if not original_path:
                    if dir_hint and os.path.isdir(dir_hint):
                        try:
                            candidates = [os.path.join(dir_hint, f) for f in os.listdir(dir_hint) if f.endswith('.webm')]
                            if candidates:
                                latest = max(candidates, key=os.path.getmtime)
                                new_path = os.path.join(dir_hint, f"tab_{seq:03d}_{url_slug}.webm")
                                if latest != new_path:
                                    os.rename(latest, new_path)
                                video_paths.append(new_path if os.path.exists(new_path) else latest)
                                continue
                        except Exception:
                            pass
                    continue

                base_dir = dir_hint if (dir_hint and os.path.exists(dir_hint)) else self._base_video_dir
                os.makedirs(base_dir, exist_ok=True)

                new_path = os.path.join(base_dir, f"tab_{seq:03d}_{url_slug}.webm")
                try:
                    if os.path.exists(original_path):
                        if original_path != new_path:
                            os.rename(original_path, new_path)
                        video_paths.append(new_path)
                    elif os.path.exists(new_path):
                        video_paths.append(new_path)
                    else:
                        candidates = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.endswith('.webm')]
                        if candidates:
                            latest = max(candidates, key=os.path.getmtime)
                            if latest != new_path:
                                os.rename(latest, new_path)
                            video_paths.append(new_path)
                except Exception:
                    video_paths.append(original_path)

        video_paths.sort(key=lambda p: int(re.search(r"tab_(\d{3})_", os.path.basename(p)).group(1)) if re.search(r"tab_(\d{3})_", os.path.basename(p)) else 0)
        return video_paths

    async def close(self):
        logger.info("\n[DEBUG] ===== CLOSE METHOD CALLED =====")
        video_paths = await self.save_videos()

        for ctx in set(self._get_all_contexts()):
            try:
                await ctx.close()
            except Exception:
                pass

        self._playwright_context = None
        self._playwright_contexts.clear()

        try:
            self._merged_video_path = merge_videos_in_order(
                base_videos_dir=self._base_video_dir,
                output_path="/app/src/outputdata/merged.webm"
            )
            if self._merged_video_path:
                logger.info(f"[DEBUG] Merged video created: {self._merged_video_path}")
            else:
                logger.warning("[DEBUG] Merged video not created")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to merge videos: {e}")

        return video_paths

    def _url_to_slug(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return "unknown"
            parts = parsed.netloc.split(":")[0].split(".")
            domain_part = "-".join(parts[-2:]) if len(parts) >= 2 else parsed.netloc
            path_segment = parsed.path.strip("/").split("/")[-1] or "home"
            slug = f"{domain_part}-{path_segment}"[:50]
            return re.sub(r"[^\w\-]", "", slug)
        except Exception:
            return "unknown"

