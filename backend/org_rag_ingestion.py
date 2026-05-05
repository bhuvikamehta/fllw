import os
import argparse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from domain.privacy import redact_text
from infrastructure.cohere_llm import CohereDraftingClient
from infrastructure.supabase_repo import supabase
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)

def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("Please install pypdf to read PDF files.")
    elif ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

def ingest_document(file_path: str, doc_type: str, tags: list):
    print(f"Reading {file_path}...")
    try:
        raw_text = extract_text(file_path)
    except Exception as e:
        print(f"Failed to read file: {e}")
        return
    
    # Recursive character splitting as requested:
    # 400 tokens (~1600 chars), 75 tokens overlap (~300 chars)
    # Order: double newline → single newline → sentence → word
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1600,
        chunk_overlap=300,
        separators=["\n\n", "\n", r"(?<=\. )", " ", ""]
    )
    chunks = splitter.split_text(raw_text)
    print(f"Split into {len(chunks)} chunks. Generating embeddings...")
    
    filename = os.path.basename(file_path)
    success_count = 0
    
    for i, chunk in enumerate(chunks):
        try:
            safe_chunk = redact_text(chunk)
            # Generate embeddings matching the pgvector_ctx logic.
            embedding = CohereDraftingClient.get_embedding(safe_chunk, input_type="search_document")
            
            metadata = {
                "source_filename": filename,
                "doc_type": doc_type,
                "tags": tags
            }
            
            # Insert into the org_document_embeddings table
            supabase.table('org_document_embeddings').insert({
                "content": safe_chunk,
                "embedding": embedding,
                "metadata": metadata
            }).execute()
            
            success_count += 1
        except Exception as e:
            print(f"Error inserting chunk {i+1}: {e}")
            
    print(f"Ingestion complete. Successfully stored {success_count} chunks.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Org Documents into RAG")
    parser.add_argument("file", help="Path to the document (.pdf, .txt, .md)")
    parser.add_argument("--type", default="general", help="Document type (e.g. policy, guide)")
    parser.add_argument("--tags", nargs="*", default=[], help="List of tags")
    args = parser.parse_args()
    
    ingest_document(args.file, args.type, args.tags)
