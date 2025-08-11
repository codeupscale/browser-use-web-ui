from typing import Dict, Optional
from pydantic import BaseModel

class PromptEnhancerOutput(BaseModel):

    agent_msg: str
    enhanced_prompt: str
   
    def custom_validate(self) -> Dict:
        # Keywords that indicate non-functional QA (UI/Animation etc.)
        blocking_keywords = [
            "ui", "user interface", "animations", "visual", "layout", 
            "transition", "hover effect", "color scheme", "font style",
            "font size", "parallax", "css effect", "design", "theme",
            "shadow", "responsive layout", "look and feel", "style", "alignment"
        ]

        prompt_lower = self.enhanced_prompt.lower()
        contains_blocked = any(kw in prompt_lower for kw in blocking_keywords)

        # 1. agent_msg should not be empty
        if not self.agent_msg.strip():
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Missing agent_msg.",
                "retry_prompt": "Please include a valid agent_msg explaining the prompt enhancement."
            }

        # 2. Check if enhanced prompt contains non-functional QA terms
        if contains_blocked:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Enhanced prompt contains non-functional QA terms (e.g., UI/animation).",
                "retry_prompt": "Remove references to UI, design, or animations. Focus only on functionality testing."
            }

        # ✅ All is valid
        return {
            "is_valid": True,
            "should_retry": False,
            "error": None,
            "retry_prompt": ""
        }