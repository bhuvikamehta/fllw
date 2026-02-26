import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from backend.domain.models import FollowUpEntity, EntityStatus, Channel, ActionMode, Priority

@pytest.fixture
def mock_entity():
    return FollowUpEntity(
        id=uuid4(),
        workspace_id="test_ws",
        created_by_user_id="test_user",
        source_type="email",
        source_ref="test_ref_123",
        target_contact="test@example.com",
        ask_summary="Please review the document",
        due_at=datetime.utcnow() + timedelta(days=1),
        status=EntityStatus.created,
        priority=Priority.medium,
        attempts_count=0,
        channel=Channel.email,
        mode=ActionMode.approval_required,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
