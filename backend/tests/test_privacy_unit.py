from domain.privacy import redact_context_bundle, redact_messages, redact_text


def test_redact_text_masks_common_pii():
    text = "From: Jane <jane@example.com>\nPhone +1 415 555 1212\nSSN 123-45-6789\nhttps://secret.example.com"

    redacted = redact_text(text)

    assert "jane@example.com" not in redacted
    assert "+1 415 555 1212" not in redacted
    assert "123-45-6789" not in redacted
    assert "https://secret.example.com" not in redacted
    assert "[REDACTED_HEADER]" in redacted
    assert "[PHONE]" in redacted
    assert "[SSN]" in redacted
    assert "[URL]" in redacted


def test_redact_messages_removes_authors_and_message_pii():
    messages = [{"author": "Alice", "text": "Email me at alice@example.com"}]

    redacted = redact_messages(messages)

    assert redacted == [{"author": "[THREAD_PARTICIPANT]", "text": "[PERSON] at [EMAIL]"}]


def test_redact_context_bundle_masks_lists_and_source_ref():
    bundle = {
        "sender_name": "sender@example.com",
        "semantic_context": ["Call me at +91 98765 43210"],
        "recent_context": ["Visit www.example.com"],
        "org_context": ["Account number: ABC123"],
        "metadata": {"source_ref": "thread_secret"},
    }

    redacted = redact_context_bundle(bundle)

    assert redacted["sender_name"] == "[EMAIL]"
    assert redacted["semantic_context"] == ["Call me at +[LONG_NUMBER]"]
    assert redacted["recent_context"] == ["Visit [URL]"]
    assert redacted["org_context"] == ["Account: [REDACTED_ID]"]
    assert redacted["metadata"]["source_ref"] == "[SOURCE_REF]"
