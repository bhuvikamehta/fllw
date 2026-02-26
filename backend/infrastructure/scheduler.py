import time
import logging
from ..domain.models import FollowUpEntity, EntityStatus, FollowUpEvent
from ..domain.state_machine import transition_state
from .supabase_repo import SupabaseRepository
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
        
        for entity in entities:
            # Check if reply received via some external mock/system
            # If reply -> close. (Skipped mock here, assumes ReplyDetector runs elsewhere or updates DB)
            
            # Check if due for draft generation (Initial, Follow-Up 1, Follow-Up 2)
            is_initial_due = (entity.status == EntityStatus.waiting and entity.due_at and entity.due_at.replace(tzinfo=None) <= now)
            is_followup_due = (entity.status in [EntityStatus.sent, EntityStatus.followed_up_1] and entity.next_follow_up_at and entity.next_follow_up_at.replace(tzinfo=None) <= now)
            
            if is_initial_due or is_followup_due:
                
                # Prevent generating drafts if we've hit max attempts; we should escalate instead
                if entity.attempts_count >= 2 and entity.status == EntityStatus.followed_up_2:
                    pass # handled below
                else:
                    from ..domain.skills.draft_generation import DraftGenerationSkill
                    from .gemini_llm import GeminiDraftingClient
                    from .pgvector_ctx import PgVectorContextRepository
                    
                    # Generate prompt and fetch draft
                    thread_summary = PgVectorContextRepository.retrieve_thread_summary(entity.source_ref, entity.ask_summary)
                    prompt = DraftGenerationSkill.generate_draft_prompt(entity, thread_summary)
                    draft_text = GeminiDraftingClient.generate_draft(prompt)
                    
                    # Increment attempts count if we are generating a follow-up draft (not the initial waiting one)
                    if entity.status in [EntityStatus.sent, EntityStatus.followed_up_1]:
                        entity.attempts_count += 1
                        
                    new_entity = transition_state(entity, EntityStatus.draft_ready)
                    self.save_and_log(new_entity, f"Draft generated (Attempt {new_entity.attempts_count})", {"draft": draft_text})
                    continue
            
            # Execute approved drafts
            if entity.status == EntityStatus.awaiting_approval:
                from .executors import EmailExecutorGateway, SlackExecutorGateway
                
                # Execute send
                if entity.channel.value == 'slack':
                    SlackExecutorGateway.send(entity, f"Sending out: {entity.ask_summary}")
                else:
                    EmailExecutorGateway.send(entity, f"Sending out: {entity.ask_summary}")
                
                # If this is the first sending attempt, go to "sent"
                if entity.attempts_count == 0:
                    new_entity = transition_state(entity, EntityStatus.sent)
                # If this is the first nudge
                elif entity.attempts_count == 1:
                    new_entity = transition_state(entity, EntityStatus.followed_up_1)
                # If this is the second nudge
                elif entity.attempts_count >= 2:
                    new_entity = transition_state(entity, EntityStatus.followed_up_2)
                    
                new_entity.last_sent_at = now
                new_entity.next_follow_up_at = now + timedelta(days=2) # Set next threshold to 2 days
                
                self.save_and_log(new_entity, f"Draft approved and successfully transmitted via Gateway (Status: {new_entity.status.value})")
                continue

            # Check if due for escalation (Only applies AFTER followed_up_2 timeout expires)
            if entity.status == EntityStatus.followed_up_2 and entity.next_follow_up_at:
                if entity.next_follow_up_at.replace(tzinfo=None) <= now:
                    new_entity = transition_state(entity, EntityStatus.escalated)
                    new_entity.next_follow_up_at = None
                    self.save_and_log(new_entity, "Escalated after max attempts")

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
