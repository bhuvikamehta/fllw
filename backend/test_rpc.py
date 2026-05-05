import os
from dotenv import load_dotenv
load_dotenv('.env')

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:8000")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSJ9.dummykeydummykeydummykeydummykeydummykeydum")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Let's just run the RPC directly to see what it returns
# We need a workspace_id. Let's query workspaces to find one.
res = client.table('workspaces').select('id').limit(1).execute()
if res.data:
    wid = res.data[0]['id']
    print(f"Testing with workspace {wid}")
    rpc_res = client.rpc('get_workspace_members_with_email', {'p_workspace_id': wid}).execute()
    print("RPC result:", rpc_res.data)
else:
    print("No workspaces found")
