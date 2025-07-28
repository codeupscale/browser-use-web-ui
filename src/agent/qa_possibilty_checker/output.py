from typing import Dict
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class QAPossibilityCheckerOutput(BaseModel):
    agent_msg: str
    qa_possibility: bool

    def custom_validate(self) -> Dict:
        """Custom validation for QA Possibility Checker"""
        logger.info(" \nRunning custom_validate for QAPossibilityCheckerOutput \n")

        # Phrases that indicate QA might not be possible or contradict QA possibility
        blocking_keywords = [
            "not clickable", "QA is not possible", 
            "no indication", "no visual presence", "static image", "cannot interact",
            "no display", "requires live webpage", "screenshot insufficient",
            "without the image", "unclear whether", "no mention", "does not show"
            
        ]

        msg_lower = self.agent_msg.lower()
        contains_blocking_phrase = any(kw in msg_lower for kw in blocking_keywords)

        # logger.debug(f"Agent message: {self.agent_msg}")
        # logger.debug(f"QA possibility: {self.qa_possibility}")
        # logger.debug(f"Detected blocking keyword: {contains_blocking_phrase}")

        # Case 1: Should be possible but explanation contradicts that
        if self.qa_possibility and contains_blocking_phrase:
            logger.warning(" Contradiction: QA is marked possible but message includes blocking keywords.\n")
            return {
                "is_valid": False,
                "should_retry": True,
                "error": "Contradiction: QA possible but message says it's not",
                "retry_prompt": "Please resolve the contradiction between your conclusion and explanation"
            }

        # Case 2: Not possible, but message lacks justification
        if not self.qa_possibility and not contains_blocking_phrase:
            logger.warning(" Insufficient justification: QA marked impossible but no blocking keywords found.\n")
            return {
                "is_valid": False,
                "should_retry": False,
                "error": "Insufficient justification: No blocking issues mentioned",
                "retry_prompt": "Explain *why* QA is not possible by including keywords like 'not clickable', 'no visual indication', or 'requires live webpage'. Avoid vague answers."

            }

        # Case 3: All good
        logger.info(" Validation passed: QA possibility and explanation are consistent.\n")
        return {
            "is_valid": True,
            "should_retry": False,
            "error": None,
            "retry_prompt": ""
        }
