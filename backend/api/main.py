from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .controllers.followups import router as followups_router
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

app.include_router(followups_router)

@app.on_event("startup")
def startup_event():
    """
    Starts the background scheduler loop.
    """
    from ..infrastructure.scheduler import Scheduler
    
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
