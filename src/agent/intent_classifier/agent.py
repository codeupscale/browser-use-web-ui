import logging
from .output import IntentClassifierOutput
from .prompt import agents_prompt
from ..main_agent.agent import run_main_agent
import logging
from typing import Any
from ...websocket.websocket_manager import send_ws_message
logger = logging.getLogger(__name__)

class IntentClassifierAgent:
    def __init__(self, llm: Any, user_prompt: str,message_callback=None) -> None:
        
        logger.info("Initializing IntentClassifierAgent")
        self.output_pydantic_class = IntentClassifierOutput
        self.llm = llm
        self.agent_prompt = agents_prompt
        self.user_prompt = user_prompt
        self.message_callback = message_callback

    async def run_agent(self) -> IntentClassifierOutput:
        logger.info(f"Running Intent Classifier Agent....")
        logger.info(f"run_main_agent is: {run_main_agent}")  # 🪵 This will help debug
        
        if self.message_callback:
            await self.message_callback("----------------------------")
            await self.message_callback("  '🟢 START: Intent Classifier Agent Started...' ")
            await self.message_callback(f"📥 User Input: {self.user_prompt}")

        output =await run_main_agent(
            output_pydantic_class=self.output_pydantic_class,
            agents_name="Intent Classifier Agent",
            agents_prompt=self.agent_prompt,
            input_to_prompt={
                "input": self.user_prompt
            },
            model_name=self.llm,
            message_callback=self.message_callback
        )
        
        if self.message_callback:
            await self.message_callback("Intent Classifier Agent is finished.") 
            await self.message_callback("----------------------------") 
        logger.info(f"Intent Classifier Agent finished. Output: {output}")
        return output
