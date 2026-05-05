import os
import sys
import traceback
from dotenv import load_dotenv

with open("error_log.txt", "w", encoding="utf-8") as f:
    try:
        load_dotenv('./backend/.env')
        from backend.infrastructure.supabase_repo import SupabaseRepository
        from backend.domain.models import EntityStatus
        from backend.infrastructure.graph import orchestrator

        repo = SupabaseRepository()
        entities = repo.get_by_status([EntityStatus.waiting, EntityStatus.draft_ready, EntityStatus.awaiting_approval])

        f.write(f"Found entities: {len(entities)}\n")
        f.flush()
        
        for i, e in enumerate(entities):
            f.write(f"--- Entity {i} - ID: {e.id}, Status: {e.status} ---\n")
            f.flush()
            try:
                res = orchestrator.invoke({'entity': e, 'route_action': 'none'})
                f.write(f"Success, final status: {res['entity'].status}\n")
            except Exception as ex:
                f.write("💥 ERROR CAUGHT:\n")
                traceback.print_exc(file=f)
            f.flush()
    except Exception as fatal:
        f.write("FATAL IMPORT ERROR:\n")
        traceback.print_exc(file=f)
