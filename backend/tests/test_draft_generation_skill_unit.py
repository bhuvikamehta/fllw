from domain.models import Priority
from domain.skills.draft_generation import DraftGenerationSkill


def test_prompt_redacts_pii_from_context(entity_factory):
    entity = entity_factory(
        ask_summary="Ask john@example.com to review account number: ABC12345",
        priority=Priority.high,
    )
    bundle = {
        "semantic_context": ["From: Jane <jane@example.com>\nCall +1 415 555 1212"],
        "recent_context": ["See https://example.com/private"],
        "org_context": [],
    }

    prompt = DraftGenerationSkill.generate_draft_prompt(entity, bundle)

    assert "john@example.com" not in prompt
    assert "jane@example.com" not in prompt
    assert "+1 415 555 1212" not in prompt
    assert "https://example.com/private" not in prompt
    assert "[EMAIL]" in prompt
    assert "[PHONE]" in prompt
    assert "[URL]" in prompt


def test_fallback_draft_uses_attempt_specific_wording(entity_factory):
    entity = entity_factory(attempts_count=2, ask_summary="Send the Q3 report")

    draft = DraftGenerationSkill.generate_fallback_draft(entity, {})

    assert "Following up once more" in draft
    assert "Send the Q3 report" in draft
    assert draft.endswith("Regards,")


def test_fallback_draft_applies_financial_policy_guidance(entity_factory):
    entity = entity_factory(ask_summary="Approve invoice for $12,500")
    bundle = {
        "org_context": [
            'Finance policy: amounts above $5000 must include the phrase "manager approval required". '
            'For high value, additional sentence must be included "Please prioritize this review."'
        ]
    }

    draft = DraftGenerationSkill.generate_fallback_draft(entity, bundle)

    assert "manager approval required" in draft
    assert "Please prioritize this review." in draft


def test_validate_draft_rejects_blocked_keywords():
    is_safe, reason = DraftGenerationSkill.validate_draft("Please confirm the salary changes.")

    assert is_safe is False
    assert "salary" in reason


def test_validate_draft_allows_normal_business_follow_up():
    is_safe, reason = DraftGenerationSkill.validate_draft("Please share the report when possible.")

    assert is_safe is True
    assert reason is None
