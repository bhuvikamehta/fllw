from infrastructure.supabase_repo import supabase

res = supabase.table('follow_ups').select('due_at').order('created_at', desc=True).limit(1).execute()
print(res.data)
