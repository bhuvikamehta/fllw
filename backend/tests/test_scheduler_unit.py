from datetime import datetime, timedelta

from domain.models import ActionMode, EntityStatus, SourceType
from infrastructure.scheduler import Scheduler


class FakeRepo:
    def __init__(self, entities):
        self.entities = entities
        self.saved = []
        self.events = []

    def get_by_status(self, statuses):
        return [entity for entity in self.entities if entity.status in statuses]

    def save_follow_up(self, entity):
        self.saved.append(entity)
        return entity

    def log_event(self, event):
        self.events.append(event)
        return event


def test_tick_escalates_second_follow_up_when_due(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.followed_up_2,
        next_follow_up_at=datetime.utcnow() - timedelta(minutes=1),
        last_sent_at=None,
    )
    repo = FakeRepo([entity])
    monkeypatch.setattr("infrastructure.graph.orchestrator.invoke", lambda state: state)

    Scheduler(repo=repo).tick()

    assert repo.saved[-1].status == EntityStatus.escalated
    assert repo.saved[-1].next_follow_up_at is None
    assert repo.events[-1].payload["reason"] == "Escalated after max attempts"


def test_tick_surfaces_detected_reply_as_acknowledgement_card(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.sent,
        source_type=SourceType.email,
        last_sent_at=datetime.utcnow() - timedelta(hours=2),
        current_draft=None,
    )
    repo = FakeRepo([entity])
    monkeypatch.setattr(
        "infrastructure.reply_detector.check_for_reply",
        lambda thread_id, last_sent_at, user_id: {"reply_detected": True, "reply_type": "normal"},
    )
    monkeypatch.setattr("infrastructure.graph.orchestrator.invoke", lambda state: state)

    Scheduler(repo=repo).tick()

    assert repo.saved[-1].status == EntityStatus.draft_ready
    assert repo.saved[-1].current_draft == "[REPLY_DETECTED] Normal reply found."
    assert "Normal reply detected" in repo.events[-1].payload["reason"]


def test_tick_logs_due_time_before_orchestration(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.waiting,
        source_type=SourceType.manual,
        due_at=datetime.utcnow() - timedelta(minutes=1),
        mode=ActionMode.approval_required,
    )
    repo = FakeRepo([entity])
    monkeypatch.setattr("infrastructure.graph.orchestrator.invoke", lambda state: {"entity": state["entity"]})

    Scheduler(repo=repo).tick()

    assert repo.events[0].payload["reason"] == "due_time_reached"
    assert repo.events[0].payload["action"] == "generate_draft"


def test_tick_skips_initial_email_followup_when_target_already_replied(monkeypatch, entity_factory):
    entity = entity_factory(
        status=EntityStatus.waiting,
        source_type=SourceType.email,
        due_at=datetime.utcnow() - timedelta(minutes=1),
    )
    repo = FakeRepo([entity])
    monkeypatch.setattr(
        "infrastructure.gmail_gateway.check_target_reply_after_outbound",
        lambda thread_id, user_id, target_contact: {"reply_detected": True},
    )
    invoked = {"count": 0}

    def fake_invoke(state):
        invoked["count"] += 1
        return state

    monkeypatch.setattr("infrastructure.graph.orchestrator.invoke", fake_invoke)

    Scheduler(repo=repo).tick()

    assert repo.saved[-1].status == EntityStatus.draft_ready
    assert repo.saved[-1].current_draft == "[REPLY_DETECTED] Normal reply found."
    assert invoked["count"] == 0
