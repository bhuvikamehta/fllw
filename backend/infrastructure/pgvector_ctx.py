import os
import google.generativeai as genai
from .supabase_repo import supabase
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "dummy_key"))

class PgVectorContextRepository:
    """
    Retrieves vector embeddings for contextual drafts using pgvector and Gemini.
    """
    @staticmethod
    def get_embedding(text: str) -> list[float]:
        try:
            # Using gemini-embedding-001 as it's universally available and truncating to 768 dimensions
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768
            )
            return result['embedding']
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    @staticmethod
    def retrieve_thread_summary(source_ref: str, ask_summary: str) -> str:
        """
        Embeds the current Ask Summary and searches `document_embeddings` 
        for the closest semantic match within this specific source_ref thread.
        """
        query_embedding = PgVectorContextRepository.get_embedding(ask_summary)
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
            context = "\n".join([row['content'] for row in response.data])
            return f"Retrieved Context:\n{context}"
            
        except Exception as e:
            print(f"Supabase RPC error: {e}")
            return "Context retrieval failed: Database error."
            
    @staticmethod
    def store_document(source_ref: str, text: str):
        """
        Helper method to insert new emails/messages into the vector DB.
        """
        embedding = PgVectorContextRepository.get_embedding(text)
        if embedding:
            supabase.table('document_embeddings').insert({
                "source_ref": source_ref,
                "content": text,
                "embedding": embedding
            }).execute()
