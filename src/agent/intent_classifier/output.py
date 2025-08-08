from typing import Dict, Optional
from pydantic import BaseModel

class IntentClassifierOutput(BaseModel):
    agent_msg: str
    intent: bool
    modified_prompt: Optional[str] = ""

    def custom_validate(self) -> Dict:
        print("custom_validate is running in the intent classifier")

        # Blocking keywords that indicate intent is not QA/testing-related
        blocking_keywords = [
           "color", "hover", "animation", "font", "design", "appearance"
        ]

        msg_lower = self.agent_msg.lower()
        contains_blocking = any(kw in msg_lower for kw in blocking_keywords)

        # 1. agent_msg should not be empty
        if not self.agent_msg.strip():
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Missing agent_msg.",
                "retry_prompt": "Please include a valid agent_msg explaining the intent classification."
            }

        # 2. intent == False should not have a modified_prompt
        if not self.intent and self.modified_prompt:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Intent is false but modified_prompt is not empty.",
                "retry_prompt": "If the query is not QA-related, remove the modified prompt."
            }

        # 3. intent == True but contains blocking (non-QA) keywords → contradiction
        if self.intent and contains_blocking:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Contradiction: Intent marked True but message implies user wants to perform functionality (not QA).",
                "retry_prompt": "Intent should be False for functional or transactional queries. Please correct it."
            }

        # 4. intent == False but NO reason is given
        if not self.intent and "not QA" not in msg_lower and not contains_blocking:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Intent marked False, but explanation is unclear or missing.",
                "retry_prompt": "Please explain clearly why the query is not QA-related."
            }

        # ✅ All is valid
        return {
            "is_valid": True,
            "should_retry": False,
            "error": None,
            "retry_prompt": ""
        }
