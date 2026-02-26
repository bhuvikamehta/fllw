import os
from supabase import create_client, Client
from typing import List, Optional, Any
from uuid import UUID
from datetime import datetime
from dotenv import load_dotenv
from ..domain.models import FollowUpEntity, FollowUpEvent

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
        data = entity.model_dump(mode='json')
        # convert uuid to str
        data['id'] = str(data['id'])
        response = supabase.table('follow_ups').upsert(data).execute()
        return FollowUpEntity(**response.data[0])

    @staticmethod
    def get_follow_up(id: UUID) -> Optional[FollowUpEntity]:
        response = supabase.table('follow_ups').select('*').eq('id', str(id)).execute()
        if not response.data:
            return None
        return FollowUpEntity(**response.data[0])
        
    @staticmethod
    def get_by_status(status_list: List[Any]) -> List[FollowUpEntity]:
        # Convert enums to string values for the Supabase query
        string_statuses = [s.value if hasattr(s, 'value') else s for s in status_list]
        response = supabase.table('follow_ups').select('*').in_('status', string_statuses).execute()
        return [FollowUpEntity(**row) for row in response.data]
        
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
