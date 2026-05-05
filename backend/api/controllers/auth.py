from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from infrastructure.supabase_repo import supabase
from api.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserCreate):
    try:
        response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        if response.user:
            return {"message": "User registered successfully", "user": response.user}
        raise HTTPException(status_code=400, detail="Registration failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": form_data.username,
            "password": form_data.password
        })
        if response.session:
            return {
                "access_token": response.session.access_token,
                "token_type": "bearer"
            }
        raise HTTPException(status_code=400, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

import os
import base64
import hashlib
import hmac
import json
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from infrastructure.gmail_gateway import (
    SCOPES,
    get_connected_gmail_account,
    get_google_client_config,
    save_user_gmail_credentials,
)

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

def _state_secret() -> bytes:
    secret = os.getenv("GMAIL_OAUTH_STATE_SECRET") or os.getenv("SUPABASE_KEY") or "dev-gmail-state-secret"
    return secret.encode("utf-8")

def _sign_state(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_state_secret(), raw, hashlib.sha256).hexdigest()
    state = {
        "payload": base64.urlsafe_b64encode(raw).decode("utf-8"),
        "sig": sig,
    }
    return base64.urlsafe_b64encode(json.dumps(state).encode("utf-8")).decode("utf-8")

def _verify_state(state_value: str) -> dict:
    try:
        state = json.loads(base64.urlsafe_b64decode(state_value.encode("utf-8")).decode("utf-8"))
        raw = base64.urlsafe_b64decode(state["payload"].encode("utf-8"))
        expected = hmac.new(_state_secret(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, state["sig"]):
            raise ValueError("Invalid state signature")
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Gmail OAuth state: {e}")

def _normalize_frontend_url(frontend_url: str | None) -> str:
    if not frontend_url:
        return os.getenv("FRONTEND_URL", "http://localhost:3000")
    cleaned = frontend_url.rstrip("/")
    if cleaned.startswith("http://localhost:") or cleaned.startswith("http://127.0.0.1:"):
        return cleaned
    return os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.get("/login/google")
def login_google():
    try:
        supabase_url = os.getenv("SUPABASE_URL", "https://hqxjqbuppbfqenlkryql.supabase.co")
        url = f"{supabase_url}/auth/v1/authorize?provider=google&redirect_to=http://localhost:3000"
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/gmail/status")
def gmail_status(current_user = Depends(get_current_user)):
    account = get_connected_gmail_account(current_user.id)
    return {
        "connected": bool(account),
        "google_email": account.get("google_email") if account else None,
        "updated_at": account.get("updated_at") if account else None,
        "scopes": account.get("scopes") if account else [],
        "send_enabled": bool(account and 'https://www.googleapis.com/auth/gmail.send' in (account.get("scopes") or [])),
    }

@router.get("/gmail/connect")
def connect_gmail(
    frontend_url: str | None = Query(default=None),
    current_user = Depends(get_current_user)
):
    try:
        redirect_uri = os.getenv("GMAIL_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback")
        config = get_google_client_config()
        client_type = "web" if "javascript_origins" in config else "installed"
        flow = Flow.from_client_config(
            {client_type: config},
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        state = _sign_state({
            "user_id": str(current_user.id),
            "frontend_url": _normalize_frontend_url(frontend_url),
        })
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state
        )
        return {"url": authorization_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/gmail/callback")
def gmail_callback(code: str, state: str):
    try:
        payload = _verify_state(state)
        user_id = payload["user_id"]
        redirect_uri = os.getenv("GMAIL_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback")
        frontend_url = _normalize_frontend_url(payload.get("frontend_url"))

        config = get_google_client_config()
        client_type = "web" if "javascript_origins" in config else "installed"
        flow = Flow.from_client_config(
            {client_type: config},
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        save_user_gmail_credentials(user_id, creds, profile.get("emailAddress", ""))
        return RedirectResponse(url=f"{frontend_url}?gmail_connected=1")
    except Exception as e:
        frontend_url = _normalize_frontend_url(None)
        return RedirectResponse(url=f"{frontend_url}?{urlencode({'gmail_error': str(e)})}")
