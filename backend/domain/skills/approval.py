from ..models import FollowUpEntity, EntityStatus
from ..state_machine import transition_state

class FollowUpApprovalSkill:
    @staticmethod
    def approve_draft(entity: FollowUpEntity) -> FollowUpEntity:
        """
        Approves a draft follow-up and transitions its state.
        Ensures deterministic flow without side-effects.
        """
        return transition_state(entity, EntityStatus.awaiting_approval)

    @staticmethod
    def close_follow_up(entity: FollowUpEntity) -> FollowUpEntity:
        """
        Closes a follow-up directly.
        """
        return transition_state(entity, EntityStatus.closed)
