import httpx
import requests
import logging
logger = logging.getLogger(__name__)
from ..outputdata.output_data import write_data_to_file

class WebpageChecker:
    def __init__(self, url,message_callback=None) -> None:
        logger.info("Initializing WebpageChecker...")
        self.url = url
        self.message_callback = message_callback
        

    async def exists(self):
        try:
            
            if self.message_callback:
                
                await self.message_callback("🧪 Initializing Webpage Checker Agent...")
                await self.message_callback(f"🌐 Checking if the webpage {self.url} exists...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/114.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.head(self.url, headers=headers, follow_redirects=True)
                if response.status_code == 403 or response.status_code >= 400:
                    logger.warning(f"HEAD request got status {response.status_code}, trying GET instead...")
                    if self.message_callback:
                        await self.message_callback(f"⚠️ HEAD request got status {response.status_code}, trying GET instead...")
                    response = await client.get(self.url, headers=headers, follow_redirects=True)
                write_data_to_file(
                    agents_name="Webpage Checker",
                    number_of_tries=1,
                    time_taken=1,
                    user_input=self.url,
                    output=f"{response.status_code} - {response.reason_phrase}"
                )
                logger.info(f"Response: {response.status_code} - {response.reason_phrase}")
                if self.message_callback:
                    if response.status_code == 200:
                        await self.message_callback("✅ Webpage exists and is valid.")
                    else:
                        await self.message_callback(f"❌ Webpage not found. {response.status_code} - {response.reason_phrase}")
                return response.status_code == 200
        except httpx.RequestError as e:
            logger.error("Error checking URL: %s", e)
            if self.message_callback:
                await self.message_callback(f"❌ Error checking URL: {e}")
            return False
        
    