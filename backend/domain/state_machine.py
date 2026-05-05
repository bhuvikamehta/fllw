from .models import FollowUpEntity, EntityStatus
from typing import Dict, List

# Define allowed transitions for strict state machine validation
ALLOWED_TRANSITIONS: Dict[EntityStatus, List[EntityStatus]] = {
    EntityStatus.created: [EntityStatus.waiting, EntityStatus.closed],
    EntityStatus.waiting: [EntityStatus.draft_ready, EntityStatus.closed],
    EntityStatus.draft_ready: [EntityStatus.awaiting_approval, EntityStatus.waiting, EntityStatus.sent, EntityStatus.followed_up_1, EntityStatus.closed],
    EntityStatus.awaiting_approval: [EntityStatus.sent, EntityStatus.followed_up_1, EntityStatus.followed_up_2, EntityStatus.closed],
    EntityStatus.sent: [EntityStatus.followed_up_1, EntityStatus.draft_ready, EntityStatus.closed],
    EntityStatus.followed_up_1: [EntityStatus.followed_up_2, EntityStatus.draft_ready, EntityStatus.closed],
    EntityStatus.followed_up_2: [EntityStatus.escalated, EntityStatus.closed],
    EntityStatus.escalated: [EntityStatus.closed],
    EntityStatus.closed: [],
}

class InvalidStateTransitionError(Exception):
    pass

def transition_state(entity: FollowUpEntity, new_state: EntityStatus) -> FollowUpEntity:
    """
    Validates and executes a state transition for a FollowUpEntity.
    """
    current_state = entity.status
    
    if new_state not in ALLOWED_TRANSITIONS.get(current_state, []):
        raise InvalidStateTransitionError(
            f"Invalid transition from {current_state} to {new_state}. "
            f"Allowed states from {current_state} are: {ALLOWED_TRANSITIONS.get(current_state, [])}"
        )
    
    entity.status = new_state
    return entity
