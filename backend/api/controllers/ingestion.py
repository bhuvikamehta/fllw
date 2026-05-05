import os
import io
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from domain.models import IngestThreadRequest, IngestMessage
from infrastructure.cohere_llm import CohereDraftingClient
from infrastructure.pgvector_ctx import PgVectorContextRepository
from infrastructure.gmail_gateway import get_thread_messages, get_thread_details
from infrastructure.supabase_repo import supabase
from api.dependencies import get_current_user
from domain.privacy import redact_text

GeminiDraftingClient = CohereDraftingClient

router = APIRouter(prefix="/ingest", tags=["ingestion"])

@router.post("/thread")
def ingest_thread(request: IngestThreadRequest):
    try:
        if not request.messages:
            return {"status": "success", "thread_id": request.thread_id, "messages_stored": 0, "message": "No messages provided"}
            
        # 1. Convert messages to dicts for the LLM summarizer
        msg_dicts = [{"author": m.author, "text": m.text} for m in request.messages]
        
        # 2. Ask Cohere for an overall summary of the thread
        summary = GeminiDraftingClient.summarize_thread(msg_dicts)
        
        # 3. Store the overarching summary with pgvector, scoped to thread_id
        summary_text = f"THREAD SUMMARY:\n{summary}"
        PgVectorContextRepository.store_document(request.thread_id, summary_text)
        
        # 4. Store each individual message with pgvector, scoped to thread_id
        for m in request.messages:
            msg_text = f"Message from {m.author}:\n{m.text}"
            PgVectorContextRepository.store_document(request.thread_id, msg_text)
            
        return {"status": "success", "thread_id": request.thread_id, "messages_stored": len(request.messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gmail_thread/{thread_id_or_subject}")
def ingest_gmail_thread(thread_id_or_subject: str, current_user = Depends(get_current_user)):
    """
    Fetches a real Gmail thread using the Gmail API, parsing messages
    and then routing them through the default pgvector ingestion logic.
    """
    try:
        from infrastructure.gmail_gateway import get_thread_messages, find_thread_id_by_query
        import re
        
        # Determine if it's a valid Gmail thread ID or a subject
        # Valid Gmail thread IDs are usually hexadecimal strings of length ~16
        if not re.match(r"^[0-9a-fA-F]{15,20}$", thread_id_or_subject):
            actual_thread_id = find_thread_id_by_query(thread_id_or_subject, current_user.id)
            if not actual_thread_id:
                raise ValueError(f"Could not find any Gmail thread matching: {thread_id_or_subject}")
        else:
            actual_thread_id = thread_id_or_subject

        details = get_thread_details(actual_thread_id, current_user.id)
        raw_msgs = details["messages"]
        
        # Build the exact same payload structure expected by existing ingestion logic
        messages = [
            IngestMessage(author=m["author"], text=m["text"])
            for m in raw_msgs
        ]
        
        request = IngestThreadRequest(thread_id=actual_thread_id, messages=messages)
        result = ingest_thread(request)
        result.update({
            "thread_id": details["thread_id"],
            "subject": details["subject"],
            "target_email": details["target_email"],
            "ask_summary": details["ask_summary"],
        })
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch and ingest Gmail thread: {str(e)}")


@router.post("/org_document")
async def upload_org_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general"),
    tags: Optional[str] = Form(""),
    workspace_id: str = Form(...),
):
    """
    Accepts a PDF, TXT, or MD file, chunks it, generates Cohere embeddings,
    and stores every chunk in org_document_embeddings scoped to workspace_id.
    """
    allowed = {".pdf", ".txt", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: PDF, TXT, MD")

    try:
        # Write the upload to a temp file so the existing ingestion logic can read it by path
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        # Re-use the ingestion logic from org_rag_ingestion.py inline
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        # Extract text
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(tmp_path)
            raw_text = "".join(page.extract_text() + "\n" for page in reader.pages)
        else:
            with open(tmp_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

        os.unlink(tmp_path)  # clean up temp file

        # Chunk — same strategy as org_rag_ingestion.py
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1600,
            chunk_overlap=300,
            separators=["\n\n", "\n", r"(?<=\. )", " ", ""]
        )
        chunks = splitter.split_text(raw_text)

        success_count = 0
        for chunk in chunks:
            safe_chunk = redact_text(chunk)
            embedding = CohereDraftingClient.get_embedding(safe_chunk, input_type="search_document")
            supabase.table("org_document_embeddings").insert({
                "content": safe_chunk,
                "embedding": embedding,
                "workspace_id": workspace_id,
                "metadata": {
                    "source_filename": file.filename,
                    "doc_type": doc_type,
                    "tags": tag_list,
                }
            }).execute()
            success_count += 1

        return {
            "status": "success",
            "filename": file.filename,
            "chunks_stored": success_count,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/org_documents")
def list_org_documents(workspace_id: str):
    """
    Returns a deduplicated list of uploaded org documents scoped to workspace_id.
    """
    try:
        response = supabase.table("org_document_embeddings") \
            .select("id, metadata") \
            .eq("workspace_id", workspace_id) \
            .execute()

        seen = {}
        for row in (response.data or []):
            meta = row.get("metadata", {})
            fname = meta.get("source_filename", "unknown")
            if fname not in seen:
                seen[fname] = {
                    "filename": fname,
                    "doc_type": meta.get("doc_type", "general"),
                    "tags": meta.get("tags", []),
                    "chunks": 0,
                }
            seen[fname]["chunks"] += 1

        return {"documents": list(seen.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.delete("/org_document")
def delete_org_document(filename: str, workspace_id: str):
    """
    Deletes all embedding chunks for a given filename scoped to workspace_id.
    """
    try:
        response = supabase.table("org_document_embeddings") \
            .delete() \
            .eq("workspace_id", workspace_id) \
            .eq("metadata->>source_filename", filename) \
            .execute()
        deleted_count = len(response.data) if response.data else 0
        return {"status": "deleted", "filename": filename, "chunks_deleted": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/org_document/download")
def download_org_document(filename: str, workspace_id: str):
    """
    Reconstructs the document text from stored embedding chunks and returns it
    as a downloadable .txt file (original binary is not stored, only extracted text).
    """
    try:
        response = supabase.table("org_document_embeddings") \
            .select("content") \
            .eq("workspace_id", workspace_id) \
            .eq("metadata->>source_filename", filename) \
            .execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"No chunks found for '{filename}' in this workspace.")

        # Chunks were stored in insertion order; reconstruct by joining them.
        # Use a separator so chunk boundaries are visible in the output.
        full_text = "\n\n---\n\n".join(row["content"] for row in response.data)
        header = f"# {filename}\n# Reconstructed from {len(response.data)} stored chunks\n\n"
        output = (header + full_text).encode("utf-8")

        safe_name = filename.rsplit(".", 1)[0] + "_extracted.txt"
        return StreamingResponse(
            io.BytesIO(output),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
