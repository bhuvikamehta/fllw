from backend.domain.skills.creation import FollowUpCreationSkill
from backend.domain.skills.reply_detection import ReplyDetectionSkill, ReplyClassification
from backend.domain.models import FollowUpRequest, Priority

def test_creation_routing():
    req = FollowUpRequest(
        workspace_id="ws_1",
        requester_user_id="usr_1",
        source_type="email",
        source_ref="ref1",
        target_persons=["user@example.com"],
        ask_summary="Check this",
        due_date_time="2026-01-01T00:00:00Z",
        urgency=Priority.high,
        action_mode="approval_required"
    )
    entity = FollowUpCreationSkill.create_entity_from_request(req)
    # email source -> email channel
    assert entity.channel.value == "email"
    assert entity.priority == Priority.high

def test_reply_detection():
    # OOO
    assert ReplyDetectionSkill.classify_reply("I am out of office until Monday.") == ReplyClassification.auto_reply
    # Irrelevant
    assert ReplyDetectionSkill.classify_reply("Click here to unsubscribe") == ReplyClassification.irrelevant_reply
    # Meaningful
    assert ReplyDetectionSkill.classify_reply("Yes, I will get this done today.") == ReplyClassification.meaningful_reply
