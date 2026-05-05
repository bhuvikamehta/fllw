import pytest

from domain.models import EntityStatus
from domain.state_machine import InvalidStateTransitionError, transition_state


def test_created_entity_can_transition_to_waiting(mock_entity):
    updated = transition_state(mock_entity, EntityStatus.waiting)

    assert updated.status == EntityStatus.waiting


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        (EntityStatus.waiting, EntityStatus.draft_ready),
        (EntityStatus.draft_ready, EntityStatus.awaiting_approval),
        (EntityStatus.awaiting_approval, EntityStatus.sent),
        (EntityStatus.sent, EntityStatus.followed_up_1),
        (EntityStatus.followed_up_1, EntityStatus.followed_up_2),
        (EntityStatus.followed_up_2, EntityStatus.escalated),
        (EntityStatus.escalated, EntityStatus.closed),
    ],
)
def test_allowed_transitions(entity_factory, current_status, next_status):
    entity = entity_factory(status=current_status)

    updated = transition_state(entity, next_status)

    assert updated.status == next_status


def test_invalid_transition_raises(entity_factory):
    entity = entity_factory(status=EntityStatus.created)

    with pytest.raises(InvalidStateTransitionError):
        transition_state(entity, EntityStatus.escalated)


def test_closed_entity_is_terminal(entity_factory):
    entity = entity_factory(status=EntityStatus.closed)

    with pytest.raises(InvalidStateTransitionError):
        transition_state(entity, EntityStatus.waiting)
