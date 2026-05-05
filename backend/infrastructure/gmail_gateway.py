import os
import json
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr, getaddresses
from infrastructure.supabase_repo import supabase

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]

def _token_path():
    if os.path.exists('backend/token.json'):
        return 'backend/token.json'
    if os.path.exists('token.json'):
        return 'token.json'
    return None

def _credentials_path():
    if os.path.exists('backend/credentials.json'):
        return 'backend/credentials.json'
    if os.path.exists('credentials.json'):
        return 'credentials.json'
    return None

def get_google_client_config():
    env_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if env_creds:
        try:
            raw = json.loads(env_creds)
            config = raw.get('web') or raw.get('installed')
            if config:
                return config
        except json.JSONDecodeError:
            pass

    credentials_path = _credentials_path()
    if not credentials_path:
        raise Exception("Missing Google OAuth credentials.json. Please set GOOGLE_CREDENTIALS_JSON environment variable.")
    with open(credentials_path, 'r') as f:
        raw = json.load(f)
    config = raw.get('web') or raw.get('installed')
    if not config:
        raise Exception("credentials.json must contain either a web or installed OAuth client.")
    return config

def _credentials_from_db(user_id: str):
    response = supabase.table('user_google_tokens').select('*').eq('user_id', str(user_id)).execute()
    if not response.data:
        return None
    row = response.data[0]
    expiry = row.get('expiry')
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00')).replace(tzinfo=None)
    return Credentials(
        token=row.get('access_token'),
        refresh_token=row.get('refresh_token'),
        token_uri=row.get('token_uri') or 'https://oauth2.googleapis.com/token',
        client_id=row.get('client_id'),
        client_secret=row.get('client_secret'),
        scopes=row.get('scopes') or SCOPES,
        expiry=expiry
    )

def save_user_gmail_credentials(user_id: str, creds: Credentials, google_email: str):
    config = get_google_client_config()
    existing = supabase.table('user_google_tokens').select('refresh_token').eq('user_id', str(user_id)).execute()
    refresh_token = creds.refresh_token
    if not refresh_token and existing.data:
        refresh_token = existing.data[0].get('refresh_token')

    data = {
        'user_id': str(user_id),
        'google_email': google_email,
        'access_token': creds.token,
        'refresh_token': refresh_token,
        'token_uri': creds.token_uri or config.get('token_uri') or 'https://oauth2.googleapis.com/token',
        'client_id': creds.client_id or config.get('client_id'),
        'client_secret': creds.client_secret or config.get('client_secret'),
        'scopes': list(creds.scopes or SCOPES),
        'expiry': creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else None,
        'updated_at': datetime.utcnow().isoformat(),
    }
    supabase.table('user_google_tokens').upsert(data).execute()

def get_connected_gmail_account(user_id: str):
    response = supabase.table('user_google_tokens').select('google_email, expiry, scopes, updated_at').eq('user_id', str(user_id)).execute()
    if not response.data:
        return None
    return response.data[0]

def get_gmail_service(user_id: str = None):
    """Returns an authorized Gmail API service instance."""
    creds = None
    if user_id:
        creds = _credentials_from_db(user_id)
        if not creds:
            raise Exception("No Gmail account connected for this user. Please connect Gmail first.")
    else:
        token_path = _token_path()
        if token_path:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            try:
                creds.refresh(Request())
                if user_id:
                    service = build('gmail', 'v1', credentials=creds)
                    profile = service.users().getProfile(userId='me').execute()
                    save_user_gmail_credentials(user_id, creds, profile.get('emailAddress', ''))
                else:
                    token_path = _token_path()
                    if token_path:
                        with open(token_path, 'w') as token:
                            token.write(creds.to_json())
            except Exception as e:
                raise Exception(f"Failed to refresh Google API credentials: {e}. Please reconnect Gmail.")
        else:
            raise Exception("Invalid or missing Google API credentials. Please connect Gmail first.")
        
    service = build('gmail', 'v1', credentials=creds)
    return service

def _get_body_from_payload(payload):
    """
    Recursively extracts the plain text or HTML body from a Gmail message payload.
    """
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif part['mimeType'] == 'text/html':
                data = part['body'].get('data')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                    # Fallback to HTML if plain text not found, strip tags using BS4
                    return BeautifulSoup(html_content, "html.parser").get_text()
            elif 'parts' in part:
                # Nested parts (e.g. multipart/related inside multipart/alternative)
                res = _get_body_from_payload(part)
                if res:
                    return res
    else:
        # Sometimes there's no parts, just the body directly
        if payload.get('mimeType') == 'text/plain' or payload.get('mimeType') == 'text/html':
            data = payload['body'].get('data')
            if data:
                 text = base64.urlsafe_b64decode(data).decode('utf-8')
                 if payload.get('mimeType') == 'text/html':
                     text = BeautifulSoup(text, "html.parser").get_text()
                 return text
                 
    return ""

def _extract_headers(headers):
    return {header['name']: header['value'] for header in headers}

def _normalize_subject(subject: str) -> str:
    if not subject:
        return "No subject"
    cleaned = subject.strip()
    while cleaned.lower().startswith(("re:", "fwd:", "fw:")):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned or "No subject"

def _extract_email_address(header_value: str) -> str:
    return parseaddr(header_value or "")[1].lower()

def _extract_email_addresses(header_value: str) -> list[str]:
    if not header_value:
        return []
    emails = []
    for _, email in getaddresses([header_value]):
        normalized = (email or "").strip().lower()
        if normalized:
            emails.append(normalized)
    return emails

def _choose_target_email(messages: list[dict], my_email: str) -> str:
    outbound_recipients = []
    fallback_external_senders = []

    for msg in messages:
        headers = msg["headers"]
        sender_email = msg["author_email"]

        if sender_email == my_email:
            recipients = []
            recipients.extend(_extract_email_addresses(headers.get("To", "")))
            recipients.extend(_extract_email_addresses(headers.get("Cc", "")))
            for recipient in recipients:
                if recipient != my_email and recipient not in outbound_recipients:
                    outbound_recipients.append(recipient)
        elif sender_email and sender_email != my_email and sender_email not in fallback_external_senders:
            fallback_external_senders.append(sender_email)

    if outbound_recipients:
        return outbound_recipients[0]
    if fallback_external_senders:
        return fallback_external_senders[0]
    return ""

def _message_ids_from_header(header_value: str) -> list[str]:
    return re.findall(r"<[^>]+>", header_value or "")

def _choose_reply_headers(messages: list[dict]) -> tuple[str, str]:
    latest_references = ""

    for msg in reversed(messages):
        headers = msg["headers"]
        references = headers.get("References", "") or headers.get("In-Reply-To", "")
        if references and not latest_references:
            latest_references = references.strip()

        message_id = (headers.get("Message-ID") or headers.get("Message-Id") or "").strip()
        if message_id:
            refs = latest_references
            if refs:
                ref_ids = _message_ids_from_header(refs)
                if message_id not in ref_ids:
                    refs = f"{refs} {message_id}".strip()
            else:
                refs = message_id
            return message_id, refs

    ref_ids = _message_ids_from_header(latest_references)
    if ref_ids:
        return ref_ids[-1], latest_references
    return "", latest_references

_THREAD_ID_CACHE = {}

def find_thread_id_by_query(query: str, user_id: str = None):
    """
    Searches Gmail for a thread matching the given query (e.g. subject)
    and returns its thread ID. If not found, returns None.
    """
    cache_key = (str(user_id) if user_id else "legacy", query)
    if cache_key in _THREAD_ID_CACHE:
        return _THREAD_ID_CACHE[cache_key]

    service = get_gmail_service(user_id)
    results = service.users().threads().list(userId='me', q=query).execute()
    threads = results.get('threads', [])
    if threads:
         _THREAD_ID_CACHE[cache_key] = threads[0]['id']
         return threads[0]['id']
    return None

def get_thread_messages(thread_id_or_subject: str, user_id: str = None):
    """
    Given a Gmail thread_id or subject, fetches the thread and returns a list of messages.
    Returns: [{"id": msg_id, "author": sender, "text": body_text, "date": int_ms, "internalDate": string}]
    """
    import re
    if not re.match(r"^[0-9a-fA-F]{15,20}$", thread_id_or_subject):
        actual_thread_id = find_thread_id_by_query(thread_id_or_subject, user_id)
        if not actual_thread_id:
            raise ValueError(f"Could not find any Gmail thread matching: {thread_id_or_subject}")
    else:
        actual_thread_id = thread_id_or_subject

    service = get_gmail_service(user_id)
    thread = service.users().threads().get(userId='me', id=actual_thread_id).execute()
    messages_data = thread.get('messages', [])
    
    parsed_messages = []
    
    for msg in messages_data:
        # Extract headers
        headers = msg['payload'].get('headers', [])
        sender = "Unknown"
        sender_email = ""
        for h in headers:
            if h['name'] == 'From':
                sender = h['value']
                sender_email = _extract_email_address(h['value'])
                break
                
        # Extract body
        body_text = _get_body_from_payload(msg['payload'])
        if not body_text:
            body_text = msg.get('snippet', '')
            
        parsed_messages.append({
            "id": msg['id'],
            "author": sender,
            "author_email": sender_email,
            "text": body_text,
            "internalDate": msg['internalDate']
        })
        
    return parsed_messages

def get_thread_details(thread_id_or_subject: str, user_id: str = None) -> dict:
    import re

    actual_thread_id = thread_id_or_subject
    if not re.match(r"^[0-9a-fA-F]{15,20}$", thread_id_or_subject):
        actual_thread_id = find_thread_id_by_query(thread_id_or_subject, user_id)
        if not actual_thread_id:
            raise ValueError(f"Could not find any Gmail thread matching: {thread_id_or_subject}")

    service = get_gmail_service(user_id)
    thread = service.users().threads().get(userId='me', id=actual_thread_id, format='full').execute()
    messages = thread.get('messages', [])
    if not messages:
        raise ValueError("Thread has no messages.")

    profile = service.users().getProfile(userId='me').execute()
    my_email = (profile.get('emailAddress') or "").lower()

    parsed_messages = []
    for msg in messages:
        headers_map = _extract_headers(msg['payload'].get('headers', []))
        sender_header = headers_map.get('From', '')
        sender_email = _extract_email_address(sender_header)
        body_text = _get_body_from_payload(msg['payload']) or msg.get('snippet', '')
        parsed_messages.append({
            "id": msg['id'],
            "threadId": msg.get('threadId'),
            "author": sender_header or "Unknown",
            "author_email": sender_email,
            "text": body_text,
            "internalDate": msg['internalDate'],
            "headers": headers_map,
        })

    latest_message = parsed_messages[-1]
    latest_headers = latest_message["headers"]
    subject = _normalize_subject(latest_headers.get("Subject", ""))
    reply_target = _choose_target_email(parsed_messages, my_email)
    reply_message_id, reply_references = _choose_reply_headers(parsed_messages)
    if not reply_target and latest_headers.get("Reply-To"):
        reply_target = _extract_email_address(latest_headers.get("Reply-To"))
    if not reply_target and latest_headers.get("To"):
        reply_target = next(
            (email for email in _extract_email_addresses(latest_headers.get("To", "")) if email != my_email),
            ""
        )
    if not reply_target and latest_headers.get("From"):
        reply_target = _extract_email_address(latest_headers.get("From"))

    return {
        "thread_id": actual_thread_id,
        "subject": subject,
        "target_email": reply_target,
        "ask_summary": subject,
        "message_count": len(parsed_messages),
        "messages": parsed_messages,
        "my_email": my_email,
        "last_message_id_header": reply_message_id,
        "references_header": reply_references,
    }

def check_target_reply_after_outbound(thread_id_or_subject: str, user_id: str, target_email: str = "", since_ms: int | None = None) -> dict:
    details = get_thread_details(thread_id_or_subject, user_id)
    my_email = details["my_email"]
    target = (target_email or details["target_email"] or "").lower()
    messages = sorted(details["messages"], key=lambda m: int(m["internalDate"]))

    start_ms = since_ms
    if start_ms is None:
        for msg in messages:
            headers = msg["headers"]
            recipients = []
            recipients.extend(_extract_email_addresses(headers.get("To", "")))
            recipients.extend(_extract_email_addresses(headers.get("Cc", "")))
            if msg["author_email"] == my_email and (not target or target in recipients):
                start_ms = int(msg["internalDate"])

    if start_ms is None:
        return {"reply_detected": False, "reply_type": "normal"}

    for msg in messages:
        msg_ms = int(msg["internalDate"])
        author_email = msg["author_email"]
        if msg_ms <= start_ms:
            continue
        if author_email == my_email:
            continue
        if target and author_email != target:
            continue

        from .reply_detector import classify_reply_type
        reply_type = classify_reply_type(msg["text"])
        return {
            "reply_detected": True,
            "reply_type": reply_type,
            "from_email": author_email,
            "message_id": msg["id"],
        }

    return {"reply_detected": False, "reply_type": "normal"}

def send_reply_to_thread(thread_id_or_subject: str, user_id: str, reply_body: str, subject_hint: str = "") -> dict:
    account = get_connected_gmail_account(user_id)
    account_scopes = set(account.get("scopes") or []) if account else set()
    if 'https://www.googleapis.com/auth/gmail.send' not in account_scopes:
        raise ValueError("Connected Gmail account is missing send access. Please reconnect Gmail to grant the gmail.send scope.")

    details = get_thread_details(thread_id_or_subject, user_id)
    service = get_gmail_service(user_id)

    subject = details["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    if not details["target_email"]:
        raise ValueError("Could not determine the email recipient for this thread.")

    message = EmailMessage()
    message["To"] = details["target_email"]
    message["Subject"] = subject
    if details["last_message_id_header"]:
        message["In-Reply-To"] = details["last_message_id_header"]
        references = details["references_header"].strip()
        combined_references = f"{references} {details['last_message_id_header']}".strip() if references else details["last_message_id_header"]
        message["References"] = combined_references
    message.set_content(reply_body)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    payload = {
        "raw": raw_message,
        "threadId": details["thread_id"],
    }
    sent = service.users().messages().send(userId='me', body=payload).execute()
    return {
        "gmail_message_id": sent.get("id"),
        "gmail_thread_id": sent.get("threadId"),
        "target_email": details["target_email"],
        "subject": subject,
    }

def check_new_replies_since(thread_id: str, since_ms: int, my_email_address="", user_id: str = None):
    """
    Checks if there are new messages in a thread after since_ms.
    Returns a dictionary indicating if a reply was detected and from whom.
    """
    try:
        if user_id:
            return check_target_reply_after_outbound(thread_id, user_id, since_ms=since_ms)
        messages = get_thread_messages(thread_id, user_id)
    except Exception as e:
        print(f"Error fetching thread {thread_id}: {e}")
        return {"reply_detected": False, "reply_type": "normal"}

    new_messages = [m for m in messages if int(m['internalDate']) > since_ms]
    
    if not new_messages:
        return {"reply_detected": False, "reply_type": "normal"}
        
    # Check if any new message is from someone ELSE (not me)
    # If the user provides my_email_address, we use it to filter out self-replies
    # Otherwise, we just assume any new message is a reply
    if my_email_address:
         new_replies = [m for m in new_messages if my_email_address.lower() not in m['author'].lower()]
         if not new_replies:
              # Only got messages from myself, so no external reply
              return {"reply_detected": False, "reply_type": "normal"}
         else:
              # For simplicity, pass the first external reply to the classifier
              msg_text = new_replies[0]['text']
    else:
         msg_text = new_messages[0]['text']

    from .reply_detector import classify_reply_type
    reply_type = classify_reply_type(msg_text)

    return {
        "reply_detected": True,
        "reply_type": reply_type
    }
