from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

class EntityStatus(str, Enum):
    created = 'created'
    waiting = 'waiting'
    draft_ready = 'draft_ready'
    awaiting_approval = 'awaiting_approval'
    sent = 'sent'
    followed_up_1 = 'followed_up_1'
    followed_up_2 = 'followed_up_2'
    escalated = 'escalated'
    closed = 'closed'

class SourceType(str, Enum):
    email = 'email'
    meeting = 'meeting'
    task = 'task'
    manual = 'manual'

class Channel(str, Enum):
    email = 'email'
    slack = 'slack'
    unknown = 'unknown'

class ActionMode(str, Enum):
    draft_only = 'draft_only'
    approval_required = 'approval_required'
    auto_send = 'auto_send'

class Priority(str, Enum):
    low = 'low'
    medium = 'medium'
    high = 'high'
    urgent = 'urgent'

class FollowUpRequest(BaseModel):
    workspace_id: str
    requester_user_id: str
    source_type: SourceType
    source_ref: str
    target_persons: List[str] = Field(default_factory=list)
    ask_summary: str = ""
    due_date_time: str
    urgency: Priority
    action_mode: ActionMode

class FollowUpEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workspace_id: str
    created_by_user_id: str
    source_type: SourceType
    source_ref: str
    target_contact: str
    ask_summary: str
    due_at: datetime
    status: EntityStatus
    priority: Priority
    attempts_count: int = 0
    last_sent_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    current_draft: Optional[str] = None
    channel: Channel
    mode: ActionMode
    created_at: datetime
    updated_at: datetime

class FollowUpEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    follow_up_id: UUID
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime

class IngestMessage(BaseModel):
    author: str
    text: str

class IngestThreadRequest(BaseModel):
    thread_id: str
    messages: List[IngestMessage]
