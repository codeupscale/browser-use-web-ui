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
    def __init__(
        self,
        browser: 'Browser',
        config: BrowserContextConfig | None = None,
        state: Optional[BrowserContextState] = None,
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config, state=state)
        self._playwright_context: Optional[PlaywrightBrowserContext] = None
        self._playwright_contexts: List[PlaywrightBrowserContext] = []
        self._handled_pages: Set = set()
        self._base_video_dir = os.path.join("/app", "src", "outputdata", "videos")

        # Track tab ordering and metadata
        self.tab_counter = 0
        self.tab_records: dict = {}
        self.context_records: dict = {}
        self._claimed_videos: Set[str] = set()
        self._closed_tabs: List[dict] = []
        self._base_dir_cleaned: bool = False
        self._merged_video_path: Optional[str] = None

    async def _setup_context(self) -> PlaywrightBrowserContext:
        """Deprecated: Do not use. Recording is managed in _create_context."""
        logger.info("\n[DEBUG] Creating new browser context...")
        
        # Ensure base directory exists
        os.makedirs(self._base_video_dir, exist_ok=True)
        logger.info(f"[DEBUG] Base video directory: {self._base_video_dir}")
        
        # Create base context WITHOUT recording; we will migrate all real tabs to per-tab contexts
        context = await self.browser.playwright_browser.new_context()
        logger.info("[DEBUG] Base context created without recording; tabs will be migrated")
        self._playwright_contexts.append(context)
        
        # Add page event handler that migrates tabs to new contexts
        async def handle_new_page(page):
            if page in self._handled_pages:
                return

            # Always allocate a new sequence for any real tab
            seq = None

            # Determine URL
            url_to_open = page.url
            if not url_to_open or url_to_open == "about:blank":
                try:
                    await page.wait_for_event("framenavigated", timeout=8000)
                    url_to_open = page.url
                except Exception:
                    url_to_open = page.url or "about:blank"

            # Skip blank helper tabs
            if url_to_open == "about:blank":
                logger.info("[DEBUG] about:blank detected, migrating immediately to start recording")
                # Allocate sequence and migrate now so the first navigation is recorded
                self.tab_counter += 1
                seq_local = self.tab_counter
                unique_dir_local = os.path.join(self._base_video_dir, f"tab_{seq_local:03d}_initial")
                try:
                    os.makedirs(unique_dir_local, exist_ok=True)
                except Exception:
                    unique_dir_local = self._base_video_dir
                try:
                    new_ctx_local = await self.browser.playwright_browser.new_context(
                        record_video_dir=unique_dir_local,
                        record_video_size={"width": 1280, "height": 720}
                    )
                    self._playwright_contexts.append(new_ctx_local)
                    self.context_records[new_ctx_local] = {"seq": seq_local, "url": "about:blank", "dir": unique_dir_local}

                    new_page_local = await new_ctx_local.new_page()  # starts at about:blank
                    self._handled_pages.add(new_page_local)
                    self.tab_records[new_page_local] = {"seq": seq_local, "url": "about:blank", "dir": unique_dir_local}

                    def on_nav_update(ev):
                        self.tab_records[new_page_local]["url"] = ev.url
                        self.context_records[new_ctx_local]["url"] = ev.url
                    new_page_local.on("framenavigated", on_nav_update)

                    new_ctx_local.on("page", handle_new_page)
                    try:
                        await page.close()
                    except Exception:
                        pass
                    logger.info(f"[TAB {seq_local:03d}] Migrated initial about:blank to {unique_dir_local}")
                except Exception as e:
                    logger.error(f"[DEBUG] Failed immediate migration: {e}")
                return

            # Allocate a new sequence number now
            self.tab_counter += 1
            seq = self.tab_counter
            
            # Build unique directory for this tab
            url_slug = self._url_to_slug(url_to_open)
            unique_dir = os.path.join(self._base_video_dir, f"tab_{seq:03d}_{url_slug}")
            try:
                os.makedirs(unique_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"[TAB {seq:03d}] Could not create dir {unique_dir}: {e}")
                unique_dir = self._base_video_dir

            # Create new context for this tab
            try:
                new_ctx = await self.browser.playwright_browser.new_context(
                    record_video_dir=unique_dir,
                    record_video_size={"width": 1280, "height": 720}
                )
                self._playwright_contexts.append(new_ctx)
                # Track context metadata for reliable save/rename
                self.context_records[new_ctx] = {"seq": seq, "url": url_to_open, "dir": unique_dir}

                new_page = await new_ctx.new_page()
                self._handled_pages.add(new_page)
                if url_to_open and url_to_open != "about:blank":
                    await new_page.goto(url_to_open)

                # Track metadata
                self.tab_records[new_page] = {"seq": seq, "url": url_to_open, "dir": unique_dir}

                def on_nav(event):
                    self.tab_records[new_page]["url"] = event.url
                new_page.on("framenavigated", on_nav)

                # Also observe future tabs from this context
                new_ctx.on("page", handle_new_page)

                # Close original stray page
                try:
                    await page.close()
                except Exception:
                    pass

                logger.info(f"[TAB {seq:03d}] Migrated to new context -> {unique_dir}")
            except Exception as e:
                logger.error(f"[TAB {seq:03d}] Migration failed: {e}")
        
        context.on("page", handle_new_page)
        logger.info("[DEBUG] Page event handler with per-tab migration added")

        # Process any existing pages (e.g., initial page created before handler attached)
        try:
            for existing_page in list(context.pages):
                try:
                    await handle_new_page(existing_page)
                except Exception as e:
                    logger.warning(f"[DEBUG] Failed to process existing page: {e}")
        except Exception:
            pass
        
        return context

    async def setup(self):
        # No-op: recording/migration is handled in _create_context (the session context)
        logger.info("[DEBUG] setup() no-op; per-tab recording handled by _create_context")
        return None

    async def new_page(self):
        """Compatibility helper used by UI code for maximizing window.
        Delegates to the underlying Playwright context of the base library session."""
        session = await self.get_session()
        return await session.context.new_page()

    async def _create_context(self, browser: PlaywrightBrowser) -> BrowserContext:
        """Create a new browser context with per-tab migration to unique video dirs"""
        logger.info("\n[DEBUG] Creating new browser context...")
        # Clean base directory once per run so no previous videos remain
        if not self._base_dir_cleaned:
            try:
                shutil.rmtree(self._base_video_dir, ignore_errors=True)
            except Exception:
                pass
            os.makedirs(self._base_video_dir, exist_ok=True)
            self._base_dir_cleaned = True
            logger.info(f"[DEBUG] Cleaned base video directory: {self._base_video_dir}")
        else:
            os.makedirs(self._base_video_dir, exist_ok=True)
        context = await browser.new_context(
            record_video_dir=self._base_video_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        logger.info("[DEBUG] Context created with recording; per-page folders will be created on save")
        self._playwright_contexts.append(context)

        async def handle_new_page(page):
            # Assign a new sequence for this page in the single recording context
            self.tab_counter += 1
            seq = self.tab_counter
            url_now = page.url or "about:blank"
            url_slug = self._url_to_slug(url_now)
            self.tab_records[page] = {"seq": seq, "url": url_now, "dir": os.path.join(self._base_video_dir, f"tab_{seq:03d}_{url_slug}")}

            async def on_nav(_):
                self.tab_records[page]["url"] = page.url
            page.on("framenavigated", on_nav)

            async def on_close():
                info = self.tab_records.get(page) or {}
                seq_c = info.get("seq", seq)
                url_c = info.get("url", url_now)
                url_slug_c = self._url_to_slug(url_c)
                dir_c = info.get("dir") or os.path.join(self._base_video_dir, f"tab_{seq_c:03d}_{url_slug_c}")
                try:
                    os.makedirs(dir_c, exist_ok=True)
                except Exception:
                    dir_c = self._base_video_dir
                # Try direct artifact path
                try:
                    original_path = await page.video.path() if hasattr(page, "video") else None
                except Exception:
                    original_path = None
                moved = False
                if original_path and os.path.exists(original_path) and original_path not in self._claimed_videos:
                    new_name = f"tab_{seq_c:03d}_{url_slug_c}.webm"
                    new_path = os.path.join(dir_c, new_name)
                    try:
                        if original_path != new_path:
                            os.rename(original_path, new_path)
                        self._claimed_videos.add(new_path)
                        moved = True
                    except Exception:
                        pass
                if not moved:
                    # Defer to final save; remember this closed tab metadata
                    self._closed_tabs.append({"seq": seq_c, "url": url_c, "dir": dir_c})
            page.on("close", on_close)
            logger.info(f"[TAB {seq:03d}] Tracking page in single recording context: {url_now}")

        context.on("page", handle_new_page)
        logger.info("[DEBUG] Page event handler with per-tab migration added")

        # Process any existing pages immediately
        try:
            for existing_page in list(context.pages):
                try:
                    await handle_new_page(existing_page)
                except Exception as e:
                    logger.warning(f"[DEBUG] Failed to process existing page: {e}")
        except Exception:
            pass

        return context

    async def stop_video_recording(self):
        """Stop video recording for all pages across all contexts without closing contexts."""
        contexts = list(self._playwright_contexts)
        if self._playwright_context and self._playwright_context not in contexts:
            contexts.append(self._playwright_context)
        for ctx in contexts:
            pages = list(ctx.pages)
            logger.info(f"\n[DEBUG] Stopping video recording for {len(pages)} pages")
            for i, page in enumerate(pages):
                if hasattr(page, 'video'):
                    try:
                        await page.close()
                        # After closing, artifact is finalized; do not delete here
                        logger.info(f"[DEBUG] Closed page {i} to finalize video")
                    except Exception as e:
                        logger.error(f"[DEBUG] Error closing page {i}: {e}")

    async def save_videos(self) -> List[str]:
        """Save videos for all contexts, rename with sequence ordering, and return paths."""
        video_paths: List[str] = []
        contexts = list(self._playwright_contexts)
        if self._playwright_context and self._playwright_context not in contexts:
            contexts.append(self._playwright_context)

        for ctx in contexts:
            try:
                pages = list(ctx.pages)
            except Exception:
                continue

            for page in pages:
                # Prefer page-level tracking; fall back to context-level tracking
                info = self.tab_records.get(page) or {}
                seq = info.get("seq")
                url = info.get("url", "unknown")
                dir_hint = info.get("dir")
                url_slug = self._url_to_slug(url)

                # Ensure page is closed to finalize recording
                try:
                    await page.close()
                except Exception:
                    pass

                try:
                    original_path = await page.video.path() if hasattr(page, "video") else None
                except Exception:
                    original_path = None

                if not original_path:
                    # Attempt to find video placed directly in dir_hint and rename it deterministically
                    if dir_hint and os.path.isdir(dir_hint):
                        try:
                            candidates = [
                                os.path.join(dir_hint, f) for f in os.listdir(dir_hint) if f.endswith('.webm')
                            ]
                            if candidates:
                                latest = max(candidates, key=lambda p: os.path.getmtime(p))
                                base_dir = dir_hint
                                if seq is None:
                                    seq = 0
                                new_name = f"tab_{seq:03d}_{url_slug}.webm"
                                new_path = os.path.join(base_dir, new_name)
                                try:
                                    if os.path.exists(latest) and latest != new_path:
                                        os.rename(latest, new_path)
                                    video_paths.append(new_path if os.path.exists(new_path) else latest)
                                except Exception:
                                    video_paths.append(latest)
                                continue
                        except Exception:
                            pass
                    continue

                # Place final file in the configured per-tab directory
                base_dir = dir_hint if (dir_hint and os.path.exists(dir_hint)) else self._base_video_dir
                if dir_hint and not os.path.exists(dir_hint):
                    try:
                        os.makedirs(dir_hint, exist_ok=True)
                        base_dir = dir_hint
                    except Exception:
                        base_dir = self._base_video_dir

                if seq is None:
                    # Fallback if sequence wasn't tracked
                    seq = 0

                new_name = f"tab_{seq:03d}_{url_slug}.webm"
                new_path = os.path.join(base_dir, new_name)
                try:
                    if os.path.exists(original_path):
                        if original_path != new_path:
                            os.rename(original_path, new_path)
                        video_paths.append(new_path)
                    else:
                        # If artifact was already in place or under a hashed subfolder, try to pick latest
                        if os.path.exists(new_path):
                            video_paths.append(new_path)
                        else:
                            try:
                                candidates = [
                                    os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.endswith('.webm')
                                ]
                                if candidates:
                                    latest = max(candidates, key=lambda p: os.path.getmtime(p))
                                    if latest != new_path:
                                        os.rename(latest, new_path)
                                    video_paths.append(new_path)
                            except Exception:
                                pass
                except Exception:
                    # Best-effort; keep original if rename fails
                    video_paths.append(original_path)

        # Return in sorted (sequence) order
        def seq_from_path(p: str) -> int:
            m = re.search(r"tab_(\d{3})_", os.path.basename(p))
            return int(m.group(1)) if m else 0

        video_paths.sort(key=seq_from_path)
        return video_paths

    async def close(self):
        """Close all contexts and save video recordings in order."""
        logger.info("\n[DEBUG] ===== CLOSE METHOD CALLED =====")
        video_paths = await self.save_videos()
        
        # Close all contexts
        contexts = list(set(self._playwright_contexts))
        if self._playwright_context and self._playwright_context not in contexts:
            contexts.append(self._playwright_context)

        for ctx in contexts:
            try:
                await ctx.close()
            except Exception:
                pass

        self._playwright_context = None
        self._playwright_contexts = []

        # Merge all tab videos into a single file if ffmpeg is available
        try:
            self._merged_video_path = merge_videos_in_order(
                base_videos_dir=self._base_video_dir,
                output_path="/app/src/outputdata/merged.webm",
            )
            if self._merged_video_path:
                logger.info(f"[DEBUG] Merged video created at: {self._merged_video_path}")
            else:
                logger.warning("[DEBUG] Merged video was not created (no inputs or ffmpeg issue)")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to merge videos: {e}")

        return video_paths

    def _url_to_slug(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return "unknown"
            domain = parsed.netloc.split(":")[0]
            # Take last two parts of domain if present, else full
            parts = domain.split(".")
            domain_part = "-".join(parts[-2:]) if len(parts) >= 2 else domain
            path_segment = parsed.path.strip("/").split("/")[-1] or "home"
            slug = f"{domain_part}-{path_segment}"[:50]
            return re.sub(r"[^\w\-]", "", slug)
        except Exception:
            return "unknown"



