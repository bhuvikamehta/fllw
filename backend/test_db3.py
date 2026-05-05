from datetime import datetime
from infrastructure.supabase_repo import supabase
from domain.models import FollowUpEntity

res = supabase.table('follow_ups').select('*').order('created_at', desc=True).limit(1).execute()
entity = FollowUpEntity(**res.data[0])

now = datetime.utcnow()
print(f"due_at: {entity.due_at}")
print(f"due_at naive: {entity.due_at.replace(tzinfo=None)}")
print(f"now: {now}")
print(f"is due: {entity.due_at.replace(tzinfo=None) <= now}")
print(f"status: {entity.status}")
