from ..models import FollowUpEntity

class DraftGenerationSkill:
    @staticmethod
    def generate_draft_prompt(entity: FollowUpEntity, thread_summary: str) -> str:
        """
        Generates the strict template prompt to be sent to the LLM (Gemini).
        No LLM decisions here, just formatting the structural template.
        """
        attempt_context = ""
        if entity.attempts_count == 1:
            attempt_context = "This is the FIRST follow-up nudge you are sending since they haven't replied to the initial message."
        elif entity.attempts_count == 2:
            attempt_context = "This is the SECOND AND FINAL follow-up nudge before escalating. Add a slight sense of urgency."
        
        return f"""
        Draft a polite and professional follow-up message based on the following:
        
        Thread Summary: {thread_summary}
        Ask: {entity.ask_summary}
        Priority: {entity.priority.value}
        Context: {attempt_context if attempt_context else 'This is your initial message initiating the tracking.'}
        
        Rules:
        - Do not add any new commitments.
        - Be concise, but specifically reference any details from the Thread Summary (like why it's needed) to demonstrate context awareness.
        - Ensure a polite tone appropriate for a {entity.priority.value} priority follow-up.
        """
        
    @staticmethod
    def validate_draft(draft_text: str) -> bool:
        """
        Validates LLM output against guardrails before it's saved.
        """
        sensitive_keywords = ["legal", "finance", "termination", "salary", "investor"]
        text_lower = draft_text.lower()
        
        for kw in sensitive_keywords:
            if kw in text_lower:
                return False
        return True
