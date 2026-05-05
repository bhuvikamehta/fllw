from typing import Dict, Any
from enum import Enum

class ReplyClassification(str, Enum):
    meaningful_reply = "meaningful_reply"
    auto_reply = "auto_reply"
    irrelevant_reply = "irrelevant_reply"

class ReplyDetectionSkill:
    @staticmethod
    def classify_reply(text: str) -> ReplyClassification:
        """
        Pure logic to classify replies.
        In V1, we may use simple heuristics or allow the infrastructure 
        to pass structured text that this analyzes.
        """
        text_lower = text.lower()
        if "out of office" in text_lower or "ooo" in text_lower or "vacation" in text_lower:
            return ReplyClassification.auto_reply
            
        if "unsubscribe" in text_lower or "newsletter" in text_lower:
            return ReplyClassification.irrelevant_reply
            
        # Default meaningful for any actual human response in V1
        return ReplyClassification.meaningful_reply
