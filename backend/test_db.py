from infrastructure.supabase_repo import supabase

try:
    res = supabase.table('follow_ups').select('*').in_('status', ['waiting', 'draft_ready', 'awaiting_approval', 'reply_detected']).execute()
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
