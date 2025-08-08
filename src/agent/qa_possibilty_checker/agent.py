import logging
from .output import QAPossibilityCheckerOutput
from .prompt import agents_prompt
from ..main_agent.agent import run_main_agent
import logging
import asyncio
from playwright.async_api import async_playwright
import os
import base64
from openai import OpenAI
import time


logger = logging.getLogger(__name__)

class QAPossibilityChecker:
    def __init__(self, llm: str, 
                 user_prompt: str, 
                 image_file_id: str,
                 message_callback=None
                 ) -> None:
        logger.info("Initializing QAPossibilityChecker")
        self.output_pydantic_class = QAPossibilityCheckerOutput
        self.user_prompt = user_prompt
        self.agent_prompt = agents_prompt
        self.image_file_id = image_file_id 
        self.llm = llm,
        self.message_callback = message_callback

    async def run_agent(self) -> QAPossibilityCheckerOutput:

        if self.message_callback:
            await self.message_callback("----------------------------")
            await self.message_callback(" 🟢 START: QAPossibility checker Agent Started... ")
            await self.message_callback(f"📥 User Input: {self.user_prompt} and image_file_id: {self.image_file_id}")

        output =await run_main_agent(
            output_pydantic_class=self.output_pydantic_class,
            agents_name="QA POSSIBILTY CHECKER",
            agents_prompt=self.agent_prompt,
            input_to_prompt={
            "input": self.user_prompt,
            "image_file_id": self.image_file_id
            },
            model_name=self.llm,
            message_callback=self.message_callback
        )

        if self.message_callback:
            await self.message_callback("QA Possibility Checker is finished.")
            await self.message_callback("----------------------------") 
        logger.info(f"QA Possibilty Checker finished Output...: {output}")
        return output
