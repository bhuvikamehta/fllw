-- Step 1: Add workspace_id as a first-class column (not buried in JSONB)
ALTER TABLE org_document_embeddings
  ADD COLUMN IF NOT EXISTS workspace_id TEXT NOT NULL DEFAULT '';

-- Step 2: Create an index so per-workspace queries are fast
CREATE INDEX IF NOT EXISTS idx_org_doc_embeddings_workspace
  ON org_document_embeddings (workspace_id);

-- Step 3: Drop and recreate match_org_documents with a workspace filter
--         (OR REPLACE handles the case where it already exists)
CREATE OR REPLACE FUNCTION match_org_documents (
  query_embedding vector(768),
  match_threshold float,
  match_count     int,
  p_workspace_id  text        -- NEW: only search this org's documents
)
RETURNS TABLE (id uuid, content text, similarity float, metadata jsonb)
LANGUAGE sql STABLE AS $$
  SELECT id, content,
    1 - (embedding <=> query_embedding) AS similarity,
    metadata
  FROM org_document_embeddings
  WHERE workspace_id = p_workspace_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;
