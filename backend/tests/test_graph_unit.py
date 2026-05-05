from datetime import datetime, timedelta

import pytest

from domain.models import ActionMode, EntityStatus
from infrastructure import graph


def test_check_due_routes_due_waiting_entity_to_context(entity_factory):
    entity = entity_factory(
        status=EntityStatus.waiting,
        due_at=datetime.utcnow() - timedelta(minutes=1),
    )

    result = graph.check_due({"entity": entity})

    assert result["route_action"] == "get_context"
    assert result["entity"] == entity


def test_check_due_routes_awaiting_approval_to_finalize(entity_factory):
    entity = entity_factory(status=EntityStatus.awaiting_approval)

    result = graph.check_due({"entity": entity})

    assert result["route_action"] == "finalize_attempt"


def test_generate_draft_uses_provider_and_sets_draft_ready(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.waiting,
        due_at=datetime.utcnow() - timedelta(minutes=1),
    )
    monkeypatch.setattr(graph.GeminiDraftingClient, "generate_draft", lambda prompt: "Hi,\n\nPlease reply.\n\nRegards,")

    result = graph.generate_draft({
        "entity": entity,
        "context_bundle": {"semantic_context": [], "recent_context": [], "org_context": []},
    })

    assert result["entity"].status == EntityStatus.draft_ready
    assert result["entity"].current_draft == "Hi,\n\nPlease reply.\n\nRegards,"
    assert result["log_payload"]["draft"] == "Hi,\n\nPlease reply.\n\nRegards,"


def test_generate_draft_uses_fallback_when_provider_fails(monkeypatch, entity_factory):
    entity = entity_factory(status=EntityStatus.waiting)

    def fail(_prompt):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(graph.GeminiDraftingClient, "generate_draft", fail)

    result = graph.generate_draft({
        "entity": entity,
        "context_bundle": {"semantic_context": [], "recent_context": [], "org_context": []},
    })

    assert result["entity"].status == EntityStatus.draft_ready
    assert "Just following up" in result["entity"].current_draft


def test_wait_for_approval_pauses_mode_a(entity_factory):
    entity = entity_factory(status=EntityStatus.draft_ready, mode=ActionMode.approval_required)

    result = graph.wait_for_approval({"entity": entity})

    assert result["route_action"] == "end"
    assert "requires manual approval" in result["log_reason"]


def test_wait_for_approval_routes_auto_send_to_finalize(entity_factory):
    entity = entity_factory(status=EntityStatus.draft_ready, mode=ActionMode.auto_send)

    result = graph.wait_for_approval({"entity": entity})

    assert result["route_action"] == "finalize_attempt"
    assert "auto-approved" in result["log_reason"]


def test_finalize_attempt_sends_and_moves_initial_attempt_to_sent(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.awaiting_approval,
        attempts_count=0,
        current_draft="Hi",
    )
    sent = {}

    def fake_send(sent_entity, text, sender_name):
        sent["entity"] = sent_entity
        sent["text"] = text
        sent["sender_name"] = sender_name
        return {"provider": "fake", "status": "queued"}

    monkeypatch.setattr(graph.EmailExecutorGateway, "send", fake_send)

    result = graph.finalize_attempt({"entity": entity, "context_bundle": {"sender_name": "Test User"}})

    assert sent["text"] == "Hi"
    assert sent["sender_name"] == "Test User"
    assert result["entity"].status == EntityStatus.sent
    assert result["entity"].last_sent_at is not None
    assert result["log_payload"]["execution_request"]["status"] == "queued"


def test_generate_draft_rejects_unsafe_provider_output(monkeypatch, entity_factory):
    entity = entity_factory(status=EntityStatus.waiting)
    monkeypatch.setattr(graph.GeminiDraftingClient, "generate_draft", lambda prompt: "Investor salary update")

    with pytest.raises(ValueError, match="Draft guardrail triggered"):
        graph.generate_draft({
            "entity": entity,
            "context_bundle": {"semantic_context": [], "recent_context": [], "org_context": []},
        })
