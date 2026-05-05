import os
from infrastructure.supabase_repo import supabase
from dotenv import load_dotenv
from domain.privacy import redact_text
from infrastructure.cohere_llm import CohereDraftingClient

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

class PgVectorContextRepository:
    """
    Retrieves vector embeddings for contextual drafts using pgvector and Cohere.
    """
    @staticmethod
    def get_embedding(text: str, task_type: str = "retrieval_query") -> list[float]:
        try:
            safe_text = redact_text(text)
            input_type = "search_document" if task_type == "retrieval_document" else "search_query"
            return CohereDraftingClient.get_embedding(safe_text, input_type=input_type)
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    @staticmethod
    def retrieve_thread_summary(source_ref: str, ask_summary: str) -> str:
        """
        Embeds the current Ask Summary and searches `document_embeddings` 
        for the closest semantic match within this specific source_ref thread.
        """
        query_embedding = PgVectorContextRepository.get_embedding(redact_text(ask_summary))
        if not query_embedding:
            return "Context retrieval failed: Embedding error."

        try:
            # Call the Supabase RPC function we created in migrations.sql
            response = supabase.rpc(
                'match_document_embeddings', 
                {
                    'query_embedding': query_embedding,
                    'match_threshold': 0.7, # 70% similarity threshold
                    'match_count': 3,       # Retrieve top 3 chunks
                    'p_source_ref': source_ref
                }
            ).execute()
            
            if not response.data:
                return "No explicit previous context found in the thread."
                
            # Concatenate the top matching text chunks
            context = "\n".join([redact_text(row['content']) for row in response.data])
            return f"Retrieved Context:\n{context}"
            
        except Exception as e:
            print(f"Supabase RPC error: {e}")
            return "Context retrieval failed: Database error."
            
    @staticmethod
    def store_document(source_ref: str, text: str):
        """
        Helper method to insert new emails/messages into the vector DB.
        """
        safe_text = redact_text(text)
        embedding = PgVectorContextRepository.get_embedding(safe_text, task_type="retrieval_document")
        if embedding:
            supabase.table('document_embeddings').insert({
                "source_ref": source_ref,
                "content": safe_text,
                "embedding": embedding
            }).execute()
