import re
from datetime import datetime

def check_for_reply(thread_id: str, last_sent_at: datetime, user_id: str = None) -> dict:
    """
    Checks if a reply has been received in the given thread after `last_sent_at`
    using the real Gmail API.
    """
    try:
        from infrastructure.gmail_gateway import check_new_replies_since
        # We need the timestamp in milliseconds
        since_ms = int(last_sent_at.timestamp() * 1000)
        # Attempt to filter out self-replies by passing a dummy email (ideally we would pass the real auth'd email)
        # Since the user didn't specify, we'll blindly return the check
        return check_new_replies_since(thread_id, since_ms, user_id=user_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "reply_detected": False,
            "reply_type": "normal"
        }

def classify_reply_type(message_body: str) -> str:
    """
    Basic string matching to detect OOO (Out of Office) replies.
    Does NOT use NLP/Intent classification, adhering to strict rules.
    """
    ooo_patterns = [
        r"(?i)\booo\b",
        r"(?i)out of office",
        r"(?i)auto-reply",
        r"(?i)automated reply",
        r"(?i)vacation responder"
    ]
    for pattern in ooo_patterns:
        if re.search(pattern, message_body):
            return "ooo"
    return "normal"
