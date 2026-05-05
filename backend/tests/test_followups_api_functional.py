from datetime import datetime, timedelta

import pytest

from domain.models import ActionMode, EntityStatus, Priority, SourceType
from api.controllers import followups


pytestmark = pytest.mark.functional


def test_create_manual_followup_returns_waiting_entity(api_client, in_memory_repo, monkeypatch):
    repo = in_memory_repo()
    monkeypatch.setattr(followups, "repo", repo)
    payload = {
        "workspace_id": "ws_1",
        "requester_user_id": "client_supplied_user_is_ignored",
        "source_type": "manual",
        "source_ref": "manual_1",
        "target_persons": ["owner@example.com"],
        "ask_summary": "Send the launch checklist",
        "due_date_time": "2026-05-05T10:30:00Z",
        "urgency": "high",
        "action_mode": "approval_required",
    }

    response = api_client.post("/followups/create", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting"
    assert data["created_by_user_id"] == "test_user"
    assert data["target_contact"] == "owner@example.com"
    assert data["priority"] == "high"
    assert repo.saved[0].status == EntityStatus.waiting


def test_create_email_followup_rejects_active_duplicate(api_client, entity_factory, in_memory_repo, monkeypatch):
    duplicate = entity_factory(status=EntityStatus.waiting)
    repo = in_memory_repo(duplicate=duplicate)
    monkeypatch.setattr(followups, "repo", repo)
    monkeypatch.setattr(
        followups,
        "get_thread_details",
        lambda source_ref, user_id: {
            "thread_id": "abc123def456789",
            "ask_summary": "Follow up on the email",
            "target_email": "target@example.com",
        },
    )
    payload = {
        "workspace_id": "ws_1",
        "requester_user_id": "client_supplied_user_is_ignored",
        "source_type": "email",
        "source_ref": "abc123def456789",
        "target_persons": [],
        "ask_summary": "",
        "due_date_time": "2026-05-05T10:30:00Z",
        "urgency": "medium",
        "action_mode": "approval_required",
    }

    response = api_client.post("/followups/create", json=payload)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_pending_active_overdue_and_report_endpoints_filter_for_current_user(
    api_client,
    entity_factory,
    in_memory_repo,
    monkeypatch,
):
    old_waiting = entity_factory(
        created_by_user_id="test_user",
        status=EntityStatus.waiting,
        due_at=datetime.utcnow() - timedelta(days=1),
    )
    active_sent = entity_factory(created_by_user_id="test_user", status=EntityStatus.sent)
    escalated = entity_factory(created_by_user_id="test_user", status=EntityStatus.escalated)
    other_user = entity_factory(created_by_user_id="someone_else", status=EntityStatus.waiting)
    repo = in_memory_repo([old_waiting, active_sent, escalated, other_user])
    monkeypatch.setattr(followups, "repo", repo)

    pending = api_client.get("/followups/pending")
    active = api_client.get("/followups/active")
    overdue = api_client.get("/followups/overdue")
    report = api_client.get("/followups/report")

    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [str(old_waiting.id)]
    assert active.status_code == 200
    assert {item["id"] for item in active.json()} == {str(old_waiting.id), str(active_sent.id)}
    assert overdue.status_code == 200
    assert [item["id"] for item in overdue.json()] == [str(old_waiting.id)]
    assert report.status_code == 200
    assert len(report.json()["escalations"]) == 1
    assert "1 escalated item" in report.json()["blocking_you_summary"]


def test_modify_reject_reschedule_close_and_explain_followup_flow(
    api_client,
    entity_factory,
    event_factory,
    in_memory_repo,
    monkeypatch,
):
    entity = entity_factory(
        status=EntityStatus.draft_ready,
        attempts_count=0,
        current_draft="Original draft",
        mode=ActionMode.approval_required,
    )
    event = event_factory(entity.id, "due_time_reached")
    repo = in_memory_repo([entity], [event])
    monkeypatch.setattr(followups, "repo", repo)

    modified = api_client.post(f"/followups/{entity.id}/modify", json={"new_text": "Edited draft"})
    assert modified.status_code == 200
    assert modified.json()["current_draft"] == "Edited draft"
    assert repo.logged_events[-1].event_type == "draft_modified"

    explained = api_client.get(f"/followups/{entity.id}/explain")
    assert explained.status_code == 200
    assert explained.json()["reason_triggered"] == "User manually edited draft"
    assert "manually approve" in explained.json()["next_action"]

    rejected = api_client.post(f"/followups/{entity.id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "waiting"
    assert rejected.json()["current_draft"] is None

    rescheduled = api_client.post(
        f"/followups/{entity.id}/reschedule",
        json={"new_time": "2026-05-05T10:30:45Z"},
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["next_follow_up_at"].startswith("2026-05-05T10:30:00")
    assert repo.logged_events[-1].event_type == "rescheduled"

    closed = api_client.post(f"/followups/{entity.id}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


def test_modify_reject_and_close_return_errors_for_invalid_entities(
    api_client,
    entity_factory,
    in_memory_repo,
    monkeypatch,
):
    waiting = entity_factory(status=EntityStatus.waiting)
    repo = in_memory_repo([waiting])
    monkeypatch.setattr(followups, "repo", repo)

    modify = api_client.post(f"/followups/{waiting.id}/modify", json={"new_text": "Nope"})
    reject = api_client.post(f"/followups/{waiting.id}/reject")
    close_missing = api_client.post("/followups/00000000-0000-0000-0000-000000000000/close")

    assert modify.status_code == 400
    assert reject.status_code == 400
    assert close_missing.status_code == 404
