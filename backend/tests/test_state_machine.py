import pytest
from backend.domain.models import EntityStatus
from backend.domain.state_machine import transition_state, InvalidStateTransitionError

def test_valid_state_transitions(mock_entity):
    assert mock_entity.status == EntityStatus.created
    
    # Valid: created -> waiting
    entity = transition_state(mock_entity, EntityStatus.waiting)
    assert entity.status == EntityStatus.waiting

    # Valid: waiting -> draft_ready
    entity = transition_state(entity, EntityStatus.draft_ready)
    assert entity.status == EntityStatus.draft_ready

def test_invalid_state_transition(mock_entity):
    with pytest.raises(InvalidStateTransitionError):
        # Invalid: created -> sent
        transition_state(mock_entity, EntityStatus.sent)
