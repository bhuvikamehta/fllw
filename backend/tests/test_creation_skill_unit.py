from datetime import datetime, timezone

from domain.models import ActionMode, FollowUpRequest, Priority, SourceType
from domain.skills.creation import FollowUpCreationSkill


def make_request(**overrides):
    data = {
        "workspace_id": "ws_1",
        "requester_user_id": "user_1",
        "source_type": SourceType.manual,
        "source_ref": "manual_1",
        "target_persons": ["person@gmail.com"],
        "ask_summary": "Please share the project status",
        "due_date_time": "2026-05-05T10:30:00Z",
        "urgency": Priority.medium,
        "action_mode": ActionMode.approval_required,
    }
    data.update(overrides)
    return FollowUpRequest(**data)


def test_auto_send_is_kept_for_allowed_domain_and_safe_summary():
    request = make_request(action_mode=ActionMode.auto_send)

    assert FollowUpCreationSkill.validate_mode(request) == ActionMode.auto_send


def test_auto_send_falls_back_to_approval_for_disallowed_domain():
    request = make_request(
        action_mode=ActionMode.auto_send,
        target_persons=["external@vendor.com"],
    )

    assert FollowUpCreationSkill.validate_mode(request) == ActionMode.approval_required


def test_auto_send_falls_back_to_approval_for_sensitive_summary():
    request = make_request(
        action_mode=ActionMode.auto_send,
        ask_summary="Please review the confidential salary spreadsheet",
    )

    assert FollowUpCreationSkill.validate_mode(request) == ActionMode.approval_required


def test_create_entity_maps_request_fields_and_parses_due_time():
    request = make_request(
        action_mode=ActionMode.auto_send,
        target_persons=["owner@example.com"],
        due_date_time="2026-05-05T10:30:00+00:00",
        urgency=Priority.high,
    )

    entity = FollowUpCreationSkill.create_entity_from_request(request)

    assert entity.workspace_id == "ws_1"
    assert entity.created_by_user_id == "user_1"
    assert entity.target_contact == "owner@example.com"
    assert entity.priority == Priority.high
    assert entity.due_at == datetime(2026, 5, 5, 10, 30, tzinfo=timezone.utc)
    assert entity.mode == ActionMode.auto_send
