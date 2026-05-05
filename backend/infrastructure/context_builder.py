import logging
import re
from uuid import UUID
from infrastructure.supabase_repo import SupabaseRepository, supabase
from domain.privacy import redact_text

logger = logging.getLogger(__name__)

def _display_name_from_email(email: str) -> str:
    local_part = (email or "").split("@", 1)[0]
    cleaned = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) if cleaned else ""

def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 2}

def _score_org_chunk(query: str, content: str) -> int:
    query_tokens = _tokens(query)
    content_lower = (content or "").lower()
    content_tokens = _tokens(content)
    score = len(query_tokens & content_tokens)

    amount_match = re.search(r"(?:[$₹]\s*)?(\d[\d,]*(?:\.\d+)?)", query or "")
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))
        thresholds = [float(value.replace(",", "")) for value in re.findall(r"(?:[$₹]\s*)?(\d[\d,]*(?:\.\d+)?)", content or "")]
        if any(amount > threshold for threshold in thresholds):
            score += 5

    policy_terms = {"approval", "approved", "financial", "escalation", "server", "upgrade"}
    score += sum(2 for term in policy_terms if term in (query or "").lower() and term in content_lower)
    return score

def _fallback_org_context(workspace_id: str, query: str, limit: int = 3) -> list[str]:
    """
    Keyword fallback for org knowledge when vector search is unavailable or too strict.
    This keeps uploaded policy docs usable in demos even when embedding/RPC calls fail.
    """
    try:
        response = (
            supabase.table("org_document_embeddings")
            .select("content")
            .eq("workspace_id", workspace_id)
            .limit(50)
            .execute()
        )
    except Exception as e:
        logger.warning(f"Org knowledge fallback failed: {e}")
        return []

    ranked = []
    for row in response.data or []:
        content = row.get("content", "")
        score = _score_org_chunk(query, content)
        if score > 0:
            ranked.append((score, content))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [redact_text(content) for _, content in ranked[:limit]]

def get_context_bundle(follow_up_id: UUID) -> dict:
    """
    Deterministically fetches structured context before RAG. 
    Does not use vector embeddings.
    """
    repo = SupabaseRepository()
    entity = repo.get_follow_up(follow_up_id)
    if not entity:
        logger.error(f"Cannot build context bundle: entity {follow_up_id} not found.")
        return {}

    # Resolve sender's real name from Supabase auth
    sender_name = ""
    try:
        user_res = supabase.auth.admin.get_user_by_id(entity.created_by_user_id)
        if user_res and user_res.user:
            meta = user_res.user.user_metadata or {}
            sender_name = (
                meta.get("full_name")
                or meta.get("name")
                or _display_name_from_email(user_res.user.email)
                or ""
            )
    except Exception as e:
        logger.warning(f"Could not resolve sender name: {e}")
        
    try:
        from infrastructure.pgvector_ctx import PgVectorContextRepository
        query_embedding = PgVectorContextRepository.get_embedding(entity.ask_summary)
        
        # Step A - Semantic
        semantic_chunks = []
        semantic_ids = set()
        if query_embedding:
            semantic_response = supabase.rpc('match_document_embeddings', {
                'query_embedding': query_embedding,
                'match_threshold': 0.7,
                'match_count': 3,
                'p_source_ref': entity.source_ref
            }).execute()

            if semantic_response.data:
                for row in semantic_response.data:
                    semantic_chunks.append(redact_text(row['content']))
                    chunk_id = row.get('id', row['content'])
                    semantic_ids.add(chunk_id)

        # Step B - Recency
        recent_chunks = []
        if entity.source_type.value == 'email':
            try:
                from infrastructure.gmail_gateway import get_thread_messages
                # Fetch real live messages!
                live_msgs = get_thread_messages(entity.source_ref, entity.created_by_user_id)
                # Take the last 5 messages
                for msg in live_msgs[-5:]:
                    recent_chunks.append(f"Message from [THREAD_PARTICIPANT]:\n{redact_text(msg['text'])}")
            except Exception as e:
                logger.warning(f"Could not fetch live email thread for context: {e}")
                # Fallback to DB
                recent_response = supabase.table('document_embeddings').select('id, content').eq('source_ref', entity.source_ref).order('id', desc=True).limit(2).execute()
                if recent_response.data:
                    for row in recent_response.data:
                        chunk_id = row.get('id', row['content'])
                        if chunk_id not in semantic_ids:
                            recent_chunks.append(redact_text(row['content']))
        else:
            recent_response = supabase.table('document_embeddings').select('id, content').eq('source_ref', entity.source_ref).order('id', desc=True).limit(2).execute()
            if recent_response.data:
                for row in recent_response.data:
                    chunk_id = row.get('id', row['content'])
                    if chunk_id not in semantic_ids:
                        recent_chunks.append(redact_text(row['content']))
                    
        # Step C - Org Knowledge (scoped strictly to this entity's workspace)
        org_chunks = []
        try:
            if query_embedding:
                org_response = supabase.rpc('match_org_documents', {
                    'query_embedding': query_embedding,
                    'match_threshold': 0.55,
                    'match_count': 3,
                    'p_workspace_id': entity.workspace_id
                }).execute()
                if org_response.data:
                    for row in org_response.data:
                        org_chunks.append(redact_text(row['content']))
        except Exception as e:
            logger.warning(f"Org knowledge RAG failed (likely table/RPC missing): {e}")
        if not org_chunks:
            org_chunks = _fallback_org_context(entity.workspace_id, entity.ask_summary)

    except Exception as e:
        logger.error(f"Error fetching RAG context: {e}")
        semantic_chunks = []
        recent_chunks = []
        org_chunks = []
        
    bundle = {
        "ask_summary": entity.ask_summary,
        "target_contact": entity.target_contact,
        "attempt_number": entity.attempts_count,
        "last_sent_at": entity.last_sent_at.isoformat() if entity.last_sent_at else None,
        "sender_name": sender_name,
        "semantic_context": semantic_chunks,
        "recent_context": recent_chunks,
        "org_context": org_chunks,
        "metadata": {
            "source_type": entity.source_type.value,
            "source_ref": entity.source_ref,
            "priority": entity.priority.value
        }
    }
    return bundle
