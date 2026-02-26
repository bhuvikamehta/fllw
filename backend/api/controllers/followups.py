from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime

from ...domain.models import FollowUpRequest, FollowUpEntity, EntityStatus
from ...domain.skills.creation import FollowUpCreationSkill
from ...domain.skills.approval import FollowUpApprovalSkill
from ...infrastructure.supabase_repo import SupabaseRepository

router = APIRouter(prefix="/followups", tags=["followups"])
repo = SupabaseRepository()

@router.post("/create", response_model=FollowUpEntity)
def create_followup(request: FollowUpRequest):
    """
    Creates a new Follow-up Request.
    """
    entity = FollowUpCreationSkill.create_entity_from_request(request)
    
    # Transition from created to waiting so it becomes "pending" and active in the system
    from ...domain.state_machine import transition_state
    entity = transition_state(entity, EntityStatus.waiting)
    
    # Check deduplication here ideally (by source_ref, ask_summary, target_contact)
    # Mocking dedupe check for prototype
    
    saved_entity = repo.save_follow_up(entity)
    return saved_entity

@router.post("/{id}/approve", response_model=FollowUpEntity)
def approve_draft(id: UUID):
    """
    Approves a draft generated for a follow-up.
    """
    entity = repo.get_follow_up(id)
    if not entity:
        raise HTTPException(status_code=404, detail="Follow-up not found")
        
    try:
        updated_entity = FollowUpApprovalSkill.approve_draft(entity)
        return repo.save_follow_up(updated_entity)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/close", response_model=FollowUpEntity)
def close_followup(id: UUID):
    """
    Manually closes a follow-up.
    """
    entity = repo.get_follow_up(id)
    if not entity:
        raise HTTPException(status_code=404, detail="Follow-up not found")
        
    updated_entity = FollowUpApprovalSkill.close_follow_up(entity)
    return repo.save_follow_up(updated_entity)

@router.get("/pending", response_model=List[FollowUpEntity])
def get_pending():
    """Returns active, not yet sent but valid follow-ups (draft_ready, awaiting_approval, waiting)."""
    return repo.get_by_status([EntityStatus.waiting, EntityStatus.draft_ready, EntityStatus.awaiting_approval])

@router.get("/overdue", response_model=List[FollowUpEntity])
def get_overdue():
    """Returns follow-ups that passed due_at and are still pending/active."""
    active = repo.get_by_status([EntityStatus.waiting, EntityStatus.draft_ready])
    now = datetime.utcnow()
    # Replace timezoneinfo to ensure proper comparison
    return [e for e in active if e.due_at.replace(tzinfo=None) < now]

@router.get("/report")
def get_report():
    """Weekly/overall block report."""
    escalated = repo.get_by_status([EntityStatus.escalated])
    pending = repo.get_by_status([EntityStatus.waiting, EntityStatus.draft_ready, EntityStatus.awaiting_approval])
    
    return {
        "escalations": [e.model_dump(mode='json') for e in escalated],
        "blocking_you_summary": f"You have {len(pending)} pending items blocking your workflow."
    }

@router.post("/batch_overdue")
def batch_overdue():
    """Endpoint to trigger actions on overdue items (used conditionally by UI/Scheduler)."""
    return {"message": "Batch overdue process triggered"}

@router.get("/{id}/explain")
def explain_followup(id: UUID):
    """
    Explainability requirement. Exposes what is pending, who owes it, due date, why triggered, what happens next.
    """
    entity = repo.get_follow_up(id)
    if not entity:
        raise HTTPException(status_code=404, detail="Follow-up not found")
        
    events = repo.get_events_for_followup(id)
    
    return {
        "what_is_pending": entity.ask_summary,
        "who_owes_it": entity.target_contact,
        "due_date": entity.due_at,
        "why_triggered": f"Source: {entity.source_type.value}, Reference: {entity.source_ref}",
        "status": entity.status.value,
        "what_happens_next": f"Will transition to next appropriate state upon conditions hit or approval.",
        "timeline": [e.model_dump(mode='json') for e in events]
    }
