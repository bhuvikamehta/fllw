from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api.controllers.followups import router as followups_router
from api.controllers.ingestion import router as ingestion_router
from api.controllers.auth import router as auth_router
from api.controllers.workspaces import router as workspaces_router
from api.dependencies import get_current_user
from fastapi import Depends
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Follow-Up Agent API", version="1.0.0")

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In prod, allow actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global 500 handler that always injects CORS headers.
    Without this, the browser misreports a real 500 as a CORS error
    because the CORS middleware cannot attach headers to unhandled crashes.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

app.include_router(auth_router)
app.include_router(workspaces_router, dependencies=[Depends(get_current_user)])
app.include_router(followups_router, dependencies=[Depends(get_current_user)])
app.include_router(ingestion_router, dependencies=[Depends(get_current_user)])

@app.on_event("startup")
def startup_event():
    """
    Starts the background scheduler loop.
    """
    from infrastructure.scheduler import Scheduler
    
    def run_scheduler():
        scheduler = Scheduler()
        logger.info("Starting background scheduler...")
        scheduler.run_continuously()
        
    # Start scheduler daemon thread
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()

@app.get("/health")
def health_check():
    return {"status": "ok"}
