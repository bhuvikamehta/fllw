import os
from supabase import create_client, Client
from typing import List, Optional, Any
from uuid import UUID
from datetime import datetime
from dotenv import load_dotenv
from domain.models import FollowUpEntity, FollowUpEvent, EntityStatus

# Load the .env from the backend directory regardless of where uvicorn is launched
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:8000")
# Make dummy key a valid JWT format so the client won't throw SupabaseException: Invalid API key
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSJ9.dummykeydummykeydummykeydummykeydummykeydum")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseRepository:
    """
    Infrastructure strictly handling database read/writes via Supabase client.
    Does not make domain logic decisions.
    """
    
    @staticmethod
    def save_follow_up(entity: FollowUpEntity) -> FollowUpEntity:
        """
        Upserts a FollowUpEntity using only the exact columns the DB table has.
        Avoids sending unexpected fields that could cause Supabase PGRST204 errors.
        """
        data = {
            'id': str(entity.id),
            'workspace_id': entity.workspace_id,
            'created_by_user_id': entity.created_by_user_id,
            'source_type': entity.source_type.value,
            'source_ref': entity.source_ref,
            'target_contact': entity.target_contact,
            'ask_summary': entity.ask_summary,
            'due_at': entity.due_at.isoformat(),
            'status': entity.status.value,
            'priority': entity.priority.value,
            'attempts_count': entity.attempts_count,
            'last_sent_at': entity.last_sent_at.isoformat() if entity.last_sent_at else None,
            'next_follow_up_at': entity.next_follow_up_at.isoformat() if entity.next_follow_up_at else None,
            'current_draft': entity.current_draft,
            'channel': entity.channel.value,
            'mode': entity.mode.value,
            'created_at': entity.created_at.isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }
        response = supabase.table('follow_ups').upsert(data).execute()
        if not response.data:
            raise RuntimeError(f"Supabase upsert returned no data. Raw response: {response}")
        return FollowUpEntity(**response.data[0])

    @staticmethod
    def get_follow_up(id: UUID) -> Optional[FollowUpEntity]:
        response = supabase.table('follow_ups').select('*').eq('id', str(id)).execute()
        if not response.data:
            return None
        return FollowUpEntity(**response.data[0])
        
    @staticmethod
    def get_by_status(status_list: List[Any], user_id: Optional[str] = None) -> List[FollowUpEntity]:
        # Convert enums to string values for the Supabase query
        string_statuses = [s.value if hasattr(s, 'value') else s for s in status_list]
        query = supabase.table('follow_ups').select('*').in_('status', string_statuses)
        if user_id:
            query = query.eq('created_by_user_id', user_id)
        response = query.execute()
        return [FollowUpEntity(**row) for row in response.data]

    @staticmethod
    def find_active_duplicate(
        *,
        user_id: str,
        workspace_id: str,
        source_type: str,
        source_ref: str,
    ) -> Optional[FollowUpEntity]:
        active_statuses = [
            EntityStatus.created.value,
            EntityStatus.waiting.value,
            EntityStatus.draft_ready.value,
            EntityStatus.awaiting_approval.value,
            EntityStatus.sent.value,
            EntityStatus.followed_up_1.value,
            EntityStatus.followed_up_2.value,
        ]
        response = (
            supabase.table('follow_ups')
            .select('*')
            .eq('created_by_user_id', user_id)
            .eq('workspace_id', workspace_id)
            .eq('source_type', source_type)
            .eq('source_ref', source_ref)
            .in_('status', active_statuses)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return FollowUpEntity(**response.data[0])
        
    @staticmethod
    def log_event(event: FollowUpEvent) -> FollowUpEvent:
        data = event.model_dump(mode='json')
        data['id'] = str(data['id'])
        data['follow_up_id'] = str(data['follow_up_id'])
        response = supabase.table('follow_up_events').insert(data).execute()
        return FollowUpEvent(**response.data[0])

    @staticmethod
    def get_events_for_followup(follow_up_id: UUID) -> List[FollowUpEvent]:
        response = supabase.table('follow_up_events').select('*').eq('follow_up_id', str(follow_up_id)).order('created_at').execute()
        return [FollowUpEvent(**row) for row in response.data]
