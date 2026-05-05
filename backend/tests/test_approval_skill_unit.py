from datetime import datetime, timedelta

from domain.models import EntityStatus
from domain.skills.approval import FollowUpApprovalSkill


def test_approve_draft_moves_to_awaiting_approval(entity_factory):
    entity = entity_factory(status=EntityStatus.draft_ready, current_draft="Hi")

    updated = FollowUpApprovalSkill.approve_draft(entity)

    assert updated.status == EntityStatus.awaiting_approval


def test_modify_draft_changes_text_without_changing_status(entity_factory):
    entity = entity_factory(status=EntityStatus.draft_ready, current_draft="Old")

    updated = FollowUpApprovalSkill.modify_draft(entity, "New draft")

    assert updated.status == EntityStatus.draft_ready
    assert updated.current_draft == "New draft"


def test_reject_initial_draft_returns_to_waiting(entity_factory):
    entity = entity_factory(
        status=EntityStatus.draft_ready,
        attempts_count=0,
        current_draft="Draft",
    )

    updated = FollowUpApprovalSkill.reject_draft(entity)

    assert updated.status == EntityStatus.waiting
    assert updated.current_draft is None
    assert updated.due_at > datetime.utcnow()


def test_reject_follow_up_draft_rolls_back_attempt_and_schedules_next(entity_factory):
    entity = entity_factory(
        status=EntityStatus.draft_ready,
        attempts_count=1,
        current_draft="Draft",
        next_follow_up_at=datetime.utcnow() - timedelta(days=1),
    )

    updated = FollowUpApprovalSkill.reject_draft(entity)

    assert updated.status == EntityStatus.sent
    assert updated.attempts_count == 0
    assert updated.current_draft is None
    assert updated.next_follow_up_at > datetime.utcnow()


def test_close_follow_up_moves_to_closed(entity_factory):
    entity = entity_factory(status=EntityStatus.waiting)

    updated = FollowUpApprovalSkill.close_follow_up(entity)

    assert updated.status == EntityStatus.closed
