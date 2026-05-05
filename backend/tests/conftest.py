import pytest
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from domain.models import (
    ActionMode,
    Channel,
    EntityStatus,
    FollowUpEvent,
    FollowUpEntity,
    Priority,
    SourceType,
)
from api.dependencies import get_current_user
from api.main import app

@pytest.fixture
def mock_entity():
    return FollowUpEntity(
        id=uuid4(),
        workspace_id="test_ws",
        created_by_user_id="test_user",
        source_type=SourceType.email,
        source_ref="test_ref_123",
        target_contact="test@example.com",
        ask_summary="Please review the document",
        due_at=datetime.utcnow() + timedelta(days=1),
        status=EntityStatus.created,
        priority=Priority.medium,
        attempts_count=0,
        channel=Channel.email,
        mode=ActionMode.approval_required,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def entity_factory():
    def build(**overrides):
        data = {
            "id": uuid4(),
            "workspace_id": "test_ws",
            "created_by_user_id": "test_user",
            "source_type": SourceType.email,
            "source_ref": "thread_123",
            "target_contact": "target@example.com",
            "ask_summary": "Please send the status update",
            "due_at": datetime.utcnow() + timedelta(days=1),
            "status": EntityStatus.created,
            "priority": Priority.medium,
            "attempts_count": 0,
            "last_sent_at": None,
            "next_follow_up_at": None,
            "current_draft": None,
            "channel": Channel.email,
            "mode": ActionMode.approval_required,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        data.update(overrides)
        return FollowUpEntity(**data)

    return build


@pytest.fixture
def fake_user():
    return SimpleNamespace(id="test_user", email="tester@example.com")


@pytest.fixture
def api_client(fake_user):
    app.dependency_overrides[get_current_user] = lambda: fake_user
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


class InMemoryFollowUpRepo:
    def __init__(self, entities=None, events=None, duplicate=None):
        self.entities = {str(entity.id): entity for entity in (entities or [])}
        self.events = {}
        for event in events or []:
            self.events.setdefault(str(event.follow_up_id), []).append(event)
        self.duplicate = duplicate
        self.saved = []
        self.logged_events = []
        self.status_queries = []

    def save_follow_up(self, entity):
        self.entities[str(entity.id)] = entity
        self.saved.append(entity)
        return entity

    def get_follow_up(self, id):
        return self.entities.get(str(id))

    def get_by_status(self, status_list, user_id=None):
        self.status_queries.append((status_list, user_id))
        status_values = {status.value if hasattr(status, "value") else status for status in status_list}
        return [
            entity
            for entity in self.entities.values()
            if entity.status.value in status_values
            and (user_id is None or entity.created_by_user_id == user_id)
        ]

    def find_active_duplicate(self, **kwargs):
        return self.duplicate

    def log_event(self, event):
        self.events.setdefault(str(event.follow_up_id), []).append(event)
        self.logged_events.append(event)
        return event

    def get_events_for_followup(self, follow_up_id):
        return self.events.get(str(follow_up_id), [])


@pytest.fixture
def in_memory_repo():
    return InMemoryFollowUpRepo


@pytest.fixture
def event_factory():
    def build(follow_up_id, reason, event_type="test_event"):
        return FollowUpEvent(
            id=uuid4(),
            follow_up_id=follow_up_id,
            event_type=event_type,
            payload={"reason": reason},
            created_at=datetime.utcnow(),
        )

    return build
