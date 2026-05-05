import time
import logging
from domain.models import FollowUpEntity, EntityStatus, FollowUpEvent, ActionMode
from domain.state_machine import transition_state
from infrastructure.supabase_repo import SupabaseRepository
from uuid import uuid4
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Scheduler:
    """
    Drives time-based transitions without LLMs.
    Runs on a 60-second tick in a separate process or thread.
    """
    def __init__(self, repo=SupabaseRepository):
        self.repo = repo
        
    def tick(self):
        """
        Executes one cycle of the scheduler.
        """
        logger.info("Scheduler tick started.")
        # Load active follow-ups. In a real system we'd limit by due_at < now() and status in (...)
        active_statuses = [
            EntityStatus.sent, 
            EntityStatus.followed_up_1, 
            EntityStatus.followed_up_2,
            EntityStatus.waiting,
            EntityStatus.awaiting_approval
        ]
        
        entities = self.repo.get_by_status(active_statuses)
        now = datetime.utcnow()
        
        from .graph import orchestrator
        from .reply_detector import check_for_reply
        from .gmail_gateway import check_target_reply_after_outbound

        for entity in entities:
            try:
                is_escalation_due = (
                    entity.status == EntityStatus.followed_up_2
                    and entity.next_follow_up_at
                    and entity.next_follow_up_at.replace(tzinfo=None) <= now
                )
                if is_escalation_due:
                    reply_info = check_for_reply(entity.source_ref, entity.last_sent_at, entity.created_by_user_id) if entity.last_sent_at else {"reply_detected": False}
                    if reply_info.get("reply_detected"):
                        entity = transition_state(entity, EntityStatus.draft_ready)
                        entity.next_follow_up_at = None
                        entity.current_draft = "[REPLY_DETECTED] Normal reply found."
                        self.save_and_log(
                            entity,
                            f"Normal reply detected in thread: {entity.source_ref}. Waiting for user acknowledgment.",
                            {"reply_info": reply_info}
                        )
                        continue
                    entity = transition_state(entity, EntityStatus.escalated)
                    entity.next_follow_up_at = None
                    self.save_and_log(entity, "Escalated after max attempts")
                    continue

                if entity.last_sent_at and entity.status in [EntityStatus.sent, EntityStatus.followed_up_1]:
                    reply_info = check_for_reply(entity.source_ref, entity.last_sent_at, entity.created_by_user_id)
                    if reply_info.get("reply_detected"):
                        if reply_info.get("reply_type") == "ooo":
                            # OOO reply: show an acknowledgement card rather than sending more follow-ups.
                            entity = transition_state(entity, EntityStatus.draft_ready)
                            entity.current_draft = "[REPLY_DETECTED] OOO reply found."
                            self.save_and_log(entity, f"OOO reply detected in thread: {entity.source_ref}. Waiting for user acknowledgment.")
                            continue
                        else:
                            entity = transition_state(entity, EntityStatus.draft_ready)
                            entity.next_follow_up_at = None
                            entity.current_draft = "[REPLY_DETECTED] Normal reply found."
                            self.save_and_log(
                                entity,
                                f"Normal reply detected in thread: {entity.source_ref}. Waiting for user acknowledgment.",
                                {"reply_info": reply_info}
                            )
                            continue

                is_initial_due = (entity.status == EntityStatus.waiting and entity.due_at and entity.due_at.replace(tzinfo=None) <= now)
                is_followup_due = (entity.status in [EntityStatus.sent, EntityStatus.followed_up_1] and entity.next_follow_up_at and entity.next_follow_up_at.replace(tzinfo=None) <= now)

                if is_initial_due and entity.source_type.value == "email":
                    reply_info = check_target_reply_after_outbound(
                        entity.source_ref,
                        entity.created_by_user_id,
                        entity.target_contact
                    )
                    if reply_info.get("reply_detected"):
                        entity = transition_state(entity, EntityStatus.draft_ready)
                        entity.next_follow_up_at = None
                        entity.current_draft = "[REPLY_DETECTED] Normal reply found."
                        self.save_and_log(
                            entity,
                            f"Normal reply detected in thread: {entity.source_ref}. Waiting for user acknowledgment.",
                            {"reply_info": reply_info}
                        )
                        continue

                if is_initial_due or is_followup_due:
                    # Log explicitly as requested: { reason: "due_time_reached", action: "generate_draft" }
                    self.save_and_log(entity, reason="due_time_reached", extra_payload={"action": "generate_draft"})

                initial_status = entity.status
                result = orchestrator.invoke({
                    "entity": entity,
                    "thread_summary": None,
                    "route_action": "none",
                    "log_reason": None,
                    "log_payload": None
                })
                
                final_entity = result["entity"]
                log_reason = result.get("log_reason")
                
                if log_reason:
                    self.save_and_log(final_entity, log_reason, result.get("log_payload"))
                elif initial_status != final_entity.status:
                    self.save_and_log(final_entity, f"State changed to {final_entity.status.value}")
                    
            except Exception as e:
                logger.error(f"Error orchestrating entity {entity.id}: {e}")

    def save_and_log(self, entity: FollowUpEntity, reason: str, extra_payload: dict = None):
        self.repo.save_follow_up(entity)
        payload = {"reason": reason, "channel": entity.channel.value}
        if extra_payload:
            payload.update(extra_payload)
            
        event = FollowUpEvent(
            id=uuid4(),
            follow_up_id=entity.id,
            event_type=f"transition_{entity.status.value}",
            payload=payload,
            created_at=datetime.utcnow()
        )
        self.repo.log_event(event)

    def run_continuously(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time.sleep(60)
