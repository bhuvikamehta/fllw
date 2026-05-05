-- Migration SQL for Follow-up Agent V1

CREATE TYPE source_type_enum AS ENUM ('email', 'meeting', 'task', 'manual');
CREATE TYPE entity_status_enum AS ENUM ('created', 'waiting', 'draft_ready', 'awaiting_approval', 'sent', 'followed_up_1', 'followed_up_2', 'escalated', 'closed');
CREATE TYPE priority_enum AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE channel_enum AS ENUM ('email', 'slack', 'unknown');
CREATE TYPE action_mode_enum AS ENUM ('draft_only', 'approval_required', 'auto_send');

CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    join_code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
ALTER TABLE workspaces DISABLE ROW LEVEL SECURITY;

CREATE TABLE workspace_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);
ALTER TABLE workspace_users DISABLE ROW LEVEL SECURITY;

-- Function to securely fetch workspace members with their emails
CREATE OR REPLACE FUNCTION get_workspace_members_with_email(p_workspace_id UUID)
RETURNS TABLE (user_id UUID, role TEXT, created_at TIMESTAMP WITH TIME ZONE, email TEXT)
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT wu.user_id, wu.role, wu.created_at, au.email::TEXT
  FROM public.workspace_users wu
  JOIN auth.users au ON au.id = wu.user_id
  WHERE wu.workspace_id = p_workspace_id;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE follow_ups (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    created_by_user_id TEXT NOT NULL,
    source_type source_type_enum NOT NULL,
    source_ref TEXT NOT NULL,
    target_contact TEXT NOT NULL,
    ask_summary TEXT NOT NULL,
    due_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status entity_status_enum NOT NULL,
    priority priority_enum NOT NULL,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMP WITH TIME ZONE,
    next_follow_up_at TIMESTAMP WITH TIME ZONE,
    channel channel_enum NOT NULL,
    mode action_mode_enum NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE follow_up_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follow_up_id UUID NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for scheduler queries
CREATE INDEX idx_follow_ups_status_due_at ON follow_ups(status, due_at);

-- Per-user Google/Gmail OAuth tokens.
-- Apply this block in Supabase before using the in-app "Connect Gmail" flow.
CREATE TABLE IF NOT EXISTS user_google_tokens (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    google_email TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_uri TEXT NOT NULL DEFAULT 'https://oauth2.googleapis.com/token',
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT ARRAY[
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send'
    ],
    expiry TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
ALTER TABLE user_google_tokens DISABLE ROW LEVEL SECURITY;

-- Phase 2: pgvector Context Setup
create extension if not exists vector;

create table document_embeddings (
    id bigserial primary key,
    source_ref text not null, -- Links back to FollowUpRequest.source_ref
    content text not null,    -- The text payload (e.g. Email body, Slack snippet)
    embedding vector(768)     -- 768 dimensions for Gemini API embeddings
);

-- Cosine similarity search function for the RPC
create or replace function match_document_embeddings (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  p_source_ref text
)
returns table (
  id bigint,
  content text,
  similarity float
)
language sql stable
as $$
  select
    document_embeddings.id,
    document_embeddings.content,
    1 - (document_embeddings.embedding <=> query_embedding) as similarity
  from document_embeddings
  where document_embeddings.source_ref = p_source_ref -- Ensure we only look at context for THIS thread
    and 1 - (document_embeddings.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;
