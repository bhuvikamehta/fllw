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
    def modify_draft(entity: FollowUpEntity, new_text: str) -> FollowUpEntity:
        """
        Modifies a draft text but leaves it in draft_ready status.
        """
        entity.current_draft = new_text
        return entity
        
    @staticmethod
    def reject_draft(entity: FollowUpEntity) -> FollowUpEntity:
        """
        Rejects a draft, setting its next scheduled time ahead 1 day 
        and rolling back its state from draft_ready to its previous resting state.
        """
        from datetime import datetime, timedelta
        
        # Determine previous resting state based on attempts
        if entity.attempts_count == 0:
            target_state = EntityStatus.waiting
            entity.due_at = datetime.utcnow() + timedelta(days=1)
        elif entity.attempts_count == 1:
            target_state = EntityStatus.sent
            entity.attempts_count -= 1 # roll back attempt increment
            entity.next_follow_up_at = datetime.utcnow() + timedelta(days=1)
        else:
            target_state = EntityStatus.followed_up_1
            entity.attempts_count -= 1
            entity.next_follow_up_at = datetime.utcnow() + timedelta(days=1)
            
        entity.current_draft = None
        return transition_state(entity, target_state)

    @staticmethod
    def close_follow_up(entity: FollowUpEntity) -> FollowUpEntity:
        """
        Closes a follow-up directly.
        """
        return transition_state(entity, EntityStatus.closed)
