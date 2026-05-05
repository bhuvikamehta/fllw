import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
DISPLAY_EMAIL_RE = re.compile(
    r"\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3}\s*<\s*"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\s*>",
    re.IGNORECASE,
)
NAME_AT_EMAIL_RE = re.compile(
    r"\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3}\s+at\s+"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
LONG_NUMBER_RE = re.compile(r"\b(?:\d[ -]?){12,19}\b")
SENSITIVE_LABEL_RE = re.compile(
    r"\b("
    r"account|acct|aadhaar|aadhar|api[_ -]?key|card|employee|emp|iban|ifsc|"
    r"license|passport|password|pan|roll|secret|ssn|student|token"
    r")\s*(?:number|no|id|#)?\s*[:=-]\s*([A-Za-z0-9_@./+-]{3,})",
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+"
    r"\s+(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|block|sector|nagar|colony)\b"
    r"[A-Za-z0-9 ,.'-]*",
    re.IGNORECASE,
)
HEADER_RE = re.compile(r"(?im)^\s*(to|from|cc|bcc|reply-to)\s*:\s*.+$")


def redact_text(value: Any) -> str:
    """
    Masks common structured PII before text is sent to external AI services.

    This is intentionally conservative and regex-based. It catches high-risk
    structured data such as emails, phones, URLs, account-like numbers, and
    labeled IDs. It does not claim to identify every human name or free-form
    address perfectly.
    """
    text = "" if value is None else str(value)
    if not text:
        return text

    text = HEADER_RE.sub(lambda m: f"{m.group(1)}: [REDACTED_HEADER]", text)
    text = DISPLAY_EMAIL_RE.sub("[PERSON] <[EMAIL]>", text)
    text = NAME_AT_EMAIL_RE.sub("[PERSON] at [EMAIL]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[URL]", text)
    text = SSN_RE.sub("[SSN]", text)
    text = SENSITIVE_LABEL_RE.sub(lambda m: f"{m.group(1)}: [REDACTED_ID]", text)
    text = ADDRESS_RE.sub("[ADDRESS]", text)
    text = LONG_NUMBER_RE.sub("[LONG_NUMBER]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text


def redact_messages(messages: list[dict]) -> list[dict]:
    redacted = []
    for message in messages or []:
        redacted.append({
            "author": "[THREAD_PARTICIPANT]",
            "text": redact_text(message.get("text", "")),
        })
    return redacted


def redact_context_bundle(bundle: dict) -> dict:
    redacted = dict(bundle or {})
    for key in ("ask_summary", "target_contact", "sender_name"):
        if key in redacted:
            redacted[key] = redact_text(redacted[key])
    for key in ("semantic_context", "recent_context", "org_context"):
        redacted[key] = [redact_text(item) for item in redacted.get(key, [])]
    metadata = dict(redacted.get("metadata") or {})
    if "source_ref" in metadata:
        metadata["source_ref"] = "[SOURCE_REF]"
    redacted["metadata"] = metadata
    return redacted
