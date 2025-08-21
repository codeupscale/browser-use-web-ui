


import os
import logging
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext
from datetime import datetime
import shutil


import os
import shutil
import glob
import logging

logger = logging.getLogger(__name__)

class BrowserRecorder:
    pass
    # def __init__(self):
    #     # Define video directory
    #     # Paths for local development
    #     # self.video_dir = os.path.join(os.getcwd(), "outputdata", "videos")
        
    #     # Paths for Dockerized application
    #     self.video_dir = os.path.join("/app", "src", "outputdata", "videos")
        
    #     # Debug: Print video directory info
    #     print(f"🎥 Video directory: {self.video_dir}")
    #     print(f"🎥 Video directory exists: {os.path.exists(self.video_dir)}")
    #     print(f"🎥 Video directory writable: {os.access(self.video_dir, os.W_OK) if os.path.exists(self.video_dir) else 'N/A'}")
        
    #     self.context = None
    #     self.is_recording = False
    #     self.recorded_videos = []
        
    #     # Clean video directory before starting
    #     self.clean_video_directory()

    # def clean_video_directory(self):
    #     """Completely remove and recreate the video directory"""
    #     try:
    #         # Remove entire directory if it exists
    #         if os.path.exists(self.video_dir):
    #             shutil.rmtree(self.video_dir)
    #             logger.info(f"🗑️ Deleted existing video directory: {self.video_dir}")
            
    #         # Create fresh directory
    #         os.makedirs(self.video_dir, exist_ok=True)
    #         logger.info(f"📁 Created clean video directory: {self.video_dir}")
    #     except Exception as e:
    #         logger.error(f"❌ Failed to clean video directory: {e}")

    # async def setup_recording(self, browser: Browser) -> BrowserContext:
    #     """Set up video recording using Playwright Browser instance"""
    #     print(f"🎥 Setting up video recording in: the browser_recorder.py")
    #     try:
    #         # Create context with video recording
    #         self.context = await browser.new_context(
    #             record_video_dir=self.video_dir,
    #             record_video_size={"width": 1280, "height": 720}
    #         )
            
    #         self.is_recording = True
    #         logger.info(f"🎥 Video recording enabled in: {self.video_dir}")
    #         return self.context
    #     except Exception as e:
    #         logger.error(f"❌ Failed to setup video recording: {str(e)}")
    #         self.is_recording = False
    #         return await browser.new_context()
            
    # def is_video_recording(self) -> bool:
    #     print(f"🎥 Checking if video recording is active and calling in browser_recorder.py")
    #     return self.is_recording
        
    # async def save_recording(self):
    #     print("""Save recordings and get video paths in browser_recorder.py""")
    #     if self.context and self.is_recording:
    #         # Close context to finalize recordings
    #         await self.context.close()
            
    #         # Find all new video files
    #         video_files = glob.glob(os.path.join(self.video_dir, "**", "*.webm"), recursive=True)
            
    #         if video_files:
    #             self.recorded_videos = [os.path.basename(f) for f in video_files]
    #             logger.info(f"💾 Saved {len(video_files)} videos")
    #         else:
    #             logger.warning("⚠️ No video files found after recording")
    
    # def get_recorded_videos(self) -> list:
    #     """Get list of recorded video filenames"""
    #     print(f"🎥 Getting recorded videos in browser_recorder.py")
    #     return self.recorded_videos
    

    


















































#Bhai MOhsin code :i think no need of this but i am not sure    
# import os
# import logging
# from pathlib import Path
# from playwright.async_api import async_playwright, Browser, BrowserContext
# from datetime import datetime

# logger = logging.getLogger(__name__)

# class BrowserRecorder:
#     def __init__(self):
#         self.video_dir = None
#         self.context = None
#         self.is_recording = False
        

    
#     async def setup_recording(self, browser: Browser) -> BrowserContext:
#         """Set up video recording right before browser launch"""
#         try:
#             # Create videos directory in outputdata
#             self.video_dir = os.path.join(os.getcwd(), "outputdata", "videos")
#             os.makedirs(self.video_dir, exist_ok=True)
            
#             logger.info(f"\n🎥 Setting up video recording in: {self.video_dir}")
            
#             # Create context with video recording
#             self.context = await browser.new_context(
#                 record_video_dir=self.video_dir,
#                 record_video_size={"width": 1280, "height": 720}
#             )
            
#             # Verify recording is enabled
#             self.is_recording = True
#             logger.info("✅ Video recording successfully enabled")
            
#             # Add listener for new pages
#             async def on_page(page):
#                 logger.info(f"🎥 Starting recording for page: {page.url}")
#                 # Force start recording for this page
#                 await page.video.start()
                
#             self.context.on("page", on_page)
            
#             return self.context
            
#         except Exception as e:
#             logger.error(f"❌ Failed to setup video recording: {str(e)}")
#             self.is_recording = False
#             # Return regular context if recording fails
#             return await browser.new_context()
            
#     def is_video_recording(self) -> bool:
#         """Check if video recording is active"""
#         return self.is_recording
        
#     async def save_recording(self):
#         """Save the recording when browser closes"""
#         if self.context and self.is_recording:
#             try:
#                 # Get all pages
#                 pages = self.context.pages
#                 for page in pages:
#                     if page.video:
#                         # Save video for this page
#                         video_path = await page.video.path()
#                         logger.info(f"💾 Saved video recording to: {video_path}")
                        
#             except Exception as e:
#                 logger.error(f"❌ Failed to save video recording: {str(e)}") 


# def get_recorded_videos(self) -> list:
#         """Get list of recorded video paths"""
#         if not self.video_dir:
#             return []
#         return [
#             os.path.join(self.video_dir, f) 
#             for f in os.listdir(self.video_dir) 
#             if f.endswith(".webm")
#         ]
