from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from ..models import FollowUpRequest, FollowUpEntity, EntityStatus, Channel, ActionMode, Priority

class FollowUpCreationSkill:
    @staticmethod
    def create_entity_from_request(req: FollowUpRequest) -> FollowUpEntity:
        """
        Creates a new FollowUpEntity from a FollowUpRequest.
        Implements deterministic routing rules.
        """
        # Channel Selection Rule
        channel = Channel.unknown
        if req.source_type == "email":
            channel = Channel.email
        elif req.urgency in [Priority.high, Priority.urgent]: # Assuming high/urgent + internal goes to slack, we'll simplify to just checking urgency or source type.
            channel = Channel.slack
        else:
            channel = Channel.email # Default
            
        return FollowUpEntity(
            id=uuid4(),
            workspace_id=req.workspace_id,
            created_by_user_id=req.requester_user_id,
            source_type=req.source_type,
            source_ref=req.source_ref,
            target_contact=req.target_persons[0] if req.target_persons else "unknown",
            ask_summary=req.ask_summary,
            due_at=datetime.fromisoformat(req.due_date_time.replace("Z", "+00:00")) if isinstance(req.due_date_time, str) else req.due_date_time,
            status=EntityStatus.created,
            priority=req.urgency,
            attempts_count=0,
            channel=channel,
            mode=req.action_mode,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
