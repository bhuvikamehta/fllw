from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from infrastructure.supabase_repo import supabase
from api.dependencies import get_current_user
import string
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

def generate_join_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceJoin(BaseModel):
    join_code: str

@router.post("")
def create_workspace(workspace: WorkspaceCreate, user=Depends(get_current_user)):
    max_retries = 3
    
    for _ in range(max_retries):
        join_code = generate_join_code()
        try:
            # 1. Insert Workspace
            response = supabase.table('workspaces').insert({
                "name": workspace.name,
                "join_code": join_code
            }).execute()
            
            if not response.data:
                raise HTTPException(status_code=500, detail="Failed to create workspace")
                
            new_workspace = response.data[0]
            
            # 2. Add current user as admin
            user_id = user.id
            supabase.table('workspace_users').insert({
                "workspace_id": new_workspace['id'],
                "user_id": user_id,
                "role": "admin"
            }).execute()
            
            return new_workspace
            
        except Exception as e:
            # Handle unique constraint violation (code 23505 usually, but supabase wraps it)
            if 'duplicate key value violates unique constraint' in str(e).lower():
                continue # Try again with a new code
            logger.error(f"Error creating workspace: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    raise HTTPException(status_code=500, detail="Could not generate unique join code")

@router.post("/join")
def join_workspace(workspace: WorkspaceJoin, user=Depends(get_current_user)):
    try:
        # 1. Find workspace by join code
        response = supabase.table('workspaces').select('*').eq('join_code', workspace.join_code).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Workspace not found with that join code")
            
        target_workspace = response.data[0]
        
        # 2. Check if user is already in workspace
        existing = supabase.table('workspace_users').select('*').eq('workspace_id', target_workspace['id']).eq('user_id', user.id).execute()
        if existing.data:
            return {"message": "Already a member", "workspace": target_workspace}
            
        # 3. Add user
        supabase.table('workspace_users').insert({
            "workspace_id": target_workspace['id'],
            "user_id": user.id,
            "role": "user"
        }).execute()
        
        return target_workspace
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error joining workspace: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
def get_my_workspaces(user=Depends(get_current_user)):
    try:
        response = supabase.table('workspace_users').select('role, workspaces(*)').eq('user_id', user.id).execute()
        workspaces = []
        for row in response.data:
            if row.get('workspaces'):
                ws = row['workspaces']
                ws['user_role'] = row.get('role')
                workspaces.append(ws)
        return workspaces
    except Exception as e:
        logger.error(f"Error fetching user workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workspace_id}/members")
def get_workspace_members(workspace_id: str, user=Depends(get_current_user)):
    try:
        # Check if user is admin
        user_ws = supabase.table('workspace_users').select('role').eq('workspace_id', workspace_id).eq('user_id', user.id).execute()
        if not user_ws.data or user_ws.data[0]['role'] != 'admin':
            raise HTTPException(status_code=403, detail="Not authorized to view members")
            
        response = supabase.rpc('get_workspace_members_with_email', {'p_workspace_id': workspace_id}).execute()
        return response.data
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AddMemberRequest(BaseModel):
    email: str
    role: str

@router.post("/{workspace_id}/members")
def add_or_update_workspace_member(workspace_id: str, request: AddMemberRequest, user=Depends(get_current_user)):
    try:
        # Check if user is admin
        user_ws = supabase.table('workspace_users').select('role').eq('workspace_id', workspace_id).eq('user_id', user.id).execute()
        if not user_ws.data or user_ws.data[0]['role'] != 'admin':
            raise HTTPException(status_code=403, detail="Not authorized to modify members")
            
        # Try to find user in the workspace by getting all members
        members_res = supabase.rpc('get_workspace_members_with_email', {'p_workspace_id': workspace_id}).execute()
        target_user = next((m for m in members_res.data if m['email'] == request.email), None)
        
        if target_user:
            # Update role
            supabase.table('workspace_users').update({'role': request.role}).eq('workspace_id', workspace_id).eq('user_id', target_user['user_id']).execute()
            return {"message": "Member role updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Cannot add user directly by email. Please share the join code for them to join as a user, then you can promote them.")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error modifying member: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{workspace_id}/members/{target_user_id}")
def remove_workspace_member(workspace_id: str, target_user_id: str, user=Depends(get_current_user)):
    try:
        # Check if user is admin
        user_ws = supabase.table('workspace_users').select('role').eq('workspace_id', workspace_id).eq('user_id', user.id).execute()
        if not user_ws.data or user_ws.data[0]['role'] != 'admin':
            raise HTTPException(status_code=403, detail="Not authorized to remove members")
            
        if target_user_id == user.id:
            raise HTTPException(status_code=400, detail="Cannot remove yourself from the workspace")
            
        supabase.table('workspace_users').delete().eq('workspace_id', workspace_id).eq('user_id', target_user_id).execute()
        return {"message": "Member removed successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error removing member: {e}")
        raise HTTPException(status_code=500, detail=str(e))
