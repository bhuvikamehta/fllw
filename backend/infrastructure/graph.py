import operator
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from datetime import datetime, timedelta

from domain.models import FollowUpEntity, EntityStatus, ActionMode
from domain.state_machine import transition_state
from infrastructure.pgvector_ctx import PgVectorContextRepository
from infrastructure.cohere_llm import CohereDraftingClient as GeminiDraftingClient
from domain.skills.draft_generation import DraftGenerationSkill
from infrastructure.executors import EmailExecutorGateway

class GraphState(TypedDict, total=False):
    entity: FollowUpEntity
    thread_summary: Optional[str]
    context_bundle: Optional[dict]
    route_action: str
    log_reason: Optional[str]
    log_payload: Optional[dict]

def check_due(state: GraphState):
    print(f"👉 LangGraph Node executing: check_due for {state['entity'].status}")
    entity = state["entity"]
    now = datetime.utcnow()
    action = "end"
    log_reason = state.get("log_reason")
    
    is_initial_due = (entity.status == EntityStatus.waiting and entity.due_at and entity.due_at.replace(tzinfo=None) <= now)
    is_followup_due = (entity.status in [EntityStatus.sent, EntityStatus.followed_up_1] and entity.next_follow_up_at and entity.next_follow_up_at.replace(tzinfo=None) <= now)
    
    if is_initial_due or is_followup_due:
        if not (entity.attempts_count >= 2 and entity.status == EntityStatus.followed_up_2):
            action = "get_context"
    elif entity.status == EntityStatus.awaiting_approval:
        action = "finalize_attempt"
    elif entity.status == EntityStatus.followed_up_2 and entity.next_follow_up_at and entity.next_follow_up_at.replace(tzinfo=None) <= now:
        action = "end"
        entity = transition_state(entity, EntityStatus.escalated)
        entity.next_follow_up_at = None
        log_reason = "Escalated after max attempts"
        
    return {"route_action": action, "entity": entity, "log_reason": log_reason}

def get_context(state: GraphState):
    entity = state["entity"]
    from .context_builder import get_context_bundle
    bundle = get_context_bundle(entity.id)
    return {"context_bundle": bundle}

def generate_draft(state: GraphState):
    entity = state["entity"]
    bundle = state.get("context_bundle", {})
    if isinstance(bundle, dict) and bundle.get("thread_summary") and not any(
        bundle.get(key) for key in ("semantic_context", "recent_context", "org_context")
    ):
        thread_summary = bundle["thread_summary"]
        if len(thread_summary) > 20000:
            thread_summary = PgVectorContextRepository.retrieve_thread_summary(
                source_ref=entity.source_ref,
                ask_summary=entity.ask_summary,
            )
        bundle = {
            **bundle,
            "semantic_context": [thread_summary],
            "recent_context": [],
            "org_context": [],
        }
    
    if entity.status in [EntityStatus.sent, EntityStatus.followed_up_1]:
        entity.attempts_count += 1
        
    prompt = DraftGenerationSkill.generate_draft_prompt(entity, bundle)
    try:
        draft_text = GeminiDraftingClient.generate_draft(prompt)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Using deterministic fallback draft for follow-up {entity.id}: {e}"
        )
        draft_text = DraftGenerationSkill.generate_fallback_draft(entity, bundle)
    from infrastructure.executors import sanitize_email_body
    draft_text = sanitize_email_body(draft_text, bundle.get("sender_name") if isinstance(bundle, dict) else "")

    # Guardrail check — returns (bool, reason). Critical for Mode C (auto_send)
    # where there is no human approval gate before the message is sent.
    is_safe, rejection_reason = DraftGenerationSkill.validate_draft(draft_text)
    if not is_safe:
        import logging
        logging.getLogger(__name__).error(
            f"Draft REJECTED for follow-up {entity.id} (attempt {entity.attempts_count}): {rejection_reason}"
        )
        raise ValueError(f"Draft guardrail triggered: {rejection_reason}")
    
    entity = transition_state(entity, EntityStatus.draft_ready)
    entity.current_draft = draft_text
    
    return {"entity": entity, "log_reason": f"Draft generated (Attempt {entity.attempts_count})", "log_payload": {"draft": draft_text}}

def wait_for_approval(state: GraphState):
    entity = state["entity"]
    
    if entity.mode == ActionMode.auto_send:
        # Mode C: skip human gate entirely — route directly to finalize_attempt
        return {
            "entity": entity,
            "route_action": "finalize_attempt",
            "log_reason": f"Draft auto-approved by Mode C policy (Attempt {entity.attempts_count})",
            "log_payload": {"draft": entity.current_draft}
        }
    elif entity.mode == ActionMode.approval_required:
        return {
            "entity": entity,
            "route_action": "end",
            "log_reason": "Mode A policy: Draft requires manual approval. Pausing flow.",
            "log_payload": {"draft": entity.current_draft}
        }
    elif entity.mode == ActionMode.draft_only:
        return {
            "entity": entity,
            "route_action": "end",
            "log_reason": "Mode B policy: Draft generated for reference only. Pausing flow.",
            "log_payload": {"draft": entity.current_draft}
        }
        
    return {"entity": entity, "route_action": "end"}

def route_after_approval(state: GraphState):
    """Routes Mode C straight to finalize_attempt; all others stop here."""
    return state.get("route_action", "end")

def finalize_attempt(state: GraphState):
    entity = state["entity"]
    send_text = entity.current_draft if entity.current_draft else f"Falling back to original ask: {entity.ask_summary}"
    sender_name = ""
    bundle = state.get("context_bundle") or {}
    if isinstance(bundle, dict):
        sender_name = bundle.get("sender_name") or ""

    execution_request = EmailExecutorGateway.send(entity, send_text, sender_name)
        
    if entity.attempts_count == 0:
        entity = transition_state(entity, EntityStatus.sent)
    elif entity.attempts_count == 1:
        entity = transition_state(entity, EntityStatus.followed_up_1)
    elif entity.attempts_count >= 2:
        entity = transition_state(entity, EntityStatus.followed_up_2)
        
    entity.last_sent_at = datetime.utcnow()
    return {"entity": entity, "log_payload": {"execution_request": execution_request}}

def schedule_next(state: GraphState):
    entity = state["entity"]
    if entity.status == EntityStatus.escalated:
        entity.next_follow_up_at = None
    else:
        entity.next_follow_up_at = (datetime.utcnow() + timedelta(days=2)).replace(second=0, microsecond=0)
    
    # Must preserve the log_payload generated by finalize_attempt so the scheduler writes it to the DB
    current_payload = state.get("log_payload", {})
    return {"entity": entity, "log_reason": f"Draft approved and successfully emitted execution_request (Status: {entity.status.value})", "log_payload": current_payload}

def route_after_check(state: GraphState):
    action = state.get("route_action")
    if action == "get_context":
        return "get_context"
    elif action == "finalize_attempt":
        return "finalize_attempt"
    else:
        return "end"

builder = StateGraph(GraphState)
builder.add_node("check_due", check_due)
builder.add_node("get_context", get_context)
builder.add_node("generate_draft", generate_draft)
builder.add_node("wait_for_approval", wait_for_approval)
builder.add_node("finalize_attempt", finalize_attempt)
builder.add_node("schedule_next", schedule_next)

builder.set_entry_point("check_due")
builder.add_conditional_edges("check_due", route_after_check, {
    "get_context": "get_context",
    "finalize_attempt": "finalize_attempt",
    "end": END
})
builder.add_edge("get_context", "generate_draft")
builder.add_edge("generate_draft", "wait_for_approval")
builder.add_conditional_edges("wait_for_approval", route_after_approval, {
    "finalize_attempt": "finalize_attempt",
    "end": END
})
builder.add_edge("finalize_attempt", "schedule_next")
builder.add_edge("schedule_next", END)

orchestrator = builder.compile()
