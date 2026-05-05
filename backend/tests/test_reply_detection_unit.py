from domain.skills.reply_detection import ReplyClassification, ReplyDetectionSkill
from infrastructure.reply_detector import classify_reply_type


def test_reply_skill_classifies_auto_reply():
    result = ReplyDetectionSkill.classify_reply("I am out of office until Monday.")

    assert result == ReplyClassification.auto_reply


def test_reply_skill_classifies_irrelevant_reply():
    result = ReplyDetectionSkill.classify_reply("Click here to unsubscribe from this newsletter.")

    assert result == ReplyClassification.irrelevant_reply


def test_reply_skill_defaults_to_meaningful_reply():
    result = ReplyDetectionSkill.classify_reply("Thanks, I will send this today.")

    assert result == ReplyClassification.meaningful_reply


def test_infrastructure_reply_classifier_detects_ooo_patterns():
    assert classify_reply_type("Automated reply: I am on vacation responder mode") == "ooo"


def test_infrastructure_reply_classifier_returns_normal_by_default():
    assert classify_reply_type("Thanks, sending the update shortly.") == "normal"
