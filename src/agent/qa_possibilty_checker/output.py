from typing import Dict
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class QAPossibilityCheckerOutput(BaseModel):
    agent_msg: str
    qa_possibility: bool
    intent: bool  # Added: intent classification result
    modified_prompt: str = ""  # Added: modified prompt from intent classification

    def custom_validate(self) -> Dict:
        """Custom validation for QA Possibility Checker with Intent Classification"""
        logger.info(" \nRunning custom_validate for QAPossibilityCheckerOutput \n")

        # Keywords that indicate non-functional QA (UI/Animation etc.)
        intent_blocking_keywords = [
            "ui", "user interface", "animations", "visual", "layout", 
            "transition", "hover effect", "color scheme", "font style",
            "font size", "parallax", "css effect", "design", "theme",
            "shadow", "responsive layout", "look and feel", "style", "alignment"
        ]

        # Phrases that indicate QA might not be possible or contradict QA possibility
        qa_blocking_keywords = [
            "not clickable", "QA is not possible", 
            "no indication", "no visual presence", "static image", "cannot interact",
            "no display", "requires live webpage", "screenshot insufficient",
            "without the image", "unclear whether", "no mention", "does not show"
        ]

        msg_lower = self.agent_msg.lower()
        contains_qa_blocking = any(kw in msg_lower for kw in qa_blocking_keywords)
        contains_intent_blocking = any(kw in msg_lower for kw in intent_blocking_keywords)

        # Intent Classification Validation
        # 1. agent_msg should not be empty
        if not self.agent_msg.strip():
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Missing agent_msg.",
                "retry_prompt": "Please include a valid agent_msg explaining the intent classification and QA possibility."
            }

        # 2. intent == False should not have a modified_prompt or qa_possibility == True
        if not self.intent and (self.modified_prompt or self.qa_possibility):
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Intent is false but modified_prompt or qa_possibility is true.",
                "retry_prompt": "If the query is not QA-related, set qa_possibility to false and leave modified_prompt empty."
            }

        # 3. intent == True but contains blocking (non-QA) keywords → contradiction
        if self.intent and contains_intent_blocking:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Contradiction: Intent marked True but message implies user wants to perform UI/animation testing.",
                "retry_prompt": "Intent should be False for UI/animation queries. Please correct it."
            }

        # 4. intent == False but NO reason is given
        if not self.intent and "not QA" not in msg_lower and not contains_intent_blocking:
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Intent marked False, but explanation is unclear or missing.",
                "retry_prompt": "Please explain clearly why the query is not QA-related."
            }

        # QA Possibility Validation (only if intent is true)
        if self.intent:
            # Case 1: Should be possible but explanation contradicts that
            if self.qa_possibility and contains_qa_blocking:
                logger.warning(" Contradiction: QA is marked possible but message includes blocking keywords.\n")
                return {
                    "is_valid": False,
                    "should_retry": True,
                    "error": "Contradiction: QA possible but message says it's not",
                    "retry_prompt": "Please resolve the contradiction between your conclusion and explanation"
                }

            # Case 2: Not possible, but message lacks justification
            if not self.qa_possibility and not contains_qa_blocking:
                logger.warning(" Insufficient justification: QA marked impossible but no blocking keywords found.\n")
                return {
                    "is_valid": False,
                    "should_retry": False,
                    "error": "Insufficient justification: No blocking issues mentioned",
                    "retry_prompt": "Explain *why* QA is not possible by including keywords like 'not clickable', 'no visual indication', or 'requires live webpage'. Avoid vague answers."
                }

        # Case 3: All good
        logger.info(" Validation passed: Intent classification and QA possibility are consistent.\n")
        return {
            "is_valid": True,
            "should_retry": False,
            "error": None,
            "retry_prompt": ""
        }
