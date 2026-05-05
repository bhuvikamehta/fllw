import logging
import re
from abc import ABC, abstractmethod
from domain.models import FollowUpEntity
from infrastructure.gmail_gateway import send_reply_to_thread

logger = logging.getLogger(__name__)

HEADER_LINE_RE = re.compile(r"^\s*(subject|to|from|cc|bcc|date|thread\s*id)\s*:", re.IGNORECASE)

def _display_name_from_email(email: str) -> str:
    local_part = (email or "").split("@", 1)[0]
    cleaned = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) if cleaned else ""

def sanitize_email_body(content: str, sender_name: str = "") -> str:
    lines = (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if HEADER_LINE_RE.match(stripped):
            continue
        if stripped.lower().startswith(("regards,", "best regards,", "thanks,", "thank you,")):
            break
        cleaned_lines.append(line.rstrip())

    body = "\n".join(cleaned_lines).strip()
    name = sender_name or ""
    if "@" in name:
        name = _display_name_from_email(name)

    signature = "Regards,"
    if name:
        signature = f"{signature}\n{name}"

    if not body:
        body = "Hi,\n\nJust following up on this."

    return f"{body}\n\n{signature}".strip()


class BaseExecutor(ABC):
    """
    Abstract base that handles shared payload construction and logging.
    Subclasses override only platform-specific fields.
    """

    def __init__(self, entity: FollowUpEntity, content: str):
        self.entity = entity
        self.content = content

    @abstractmethod
    def _channel_label(self) -> str:
        """Return the platform name used in log messages."""

    @abstractmethod
    def _extra_fields(self) -> dict:
        """Return any platform-specific extra fields to merge into the payload."""

    def execute(self) -> dict:
        logger.info(
            f"Emitting execution_request for {self._channel_label().upper()} "
            f"to {self.entity.target_contact} for follow-up {self.entity.id}"
        )
        payload = {
            "draft_body": self.content,
            "target_contact": self.entity.target_contact,
            "channel": self.entity.channel.value,
            "metadata": {
                "follow_up_id": str(self.entity.id),
                "source_ref": self.entity.source_ref,
                "priority": self.entity.priority.value,
            },
        }
        payload.update(self._extra_fields())
        return payload


class EmailExecutor(BaseExecutor):
    def __init__(self, entity: FollowUpEntity, content: str, sender_name: str = ""):
        super().__init__(entity, content)
        self.sender_name = sender_name

    def _channel_label(self) -> str:
        return "email"

    def _extra_fields(self) -> dict:
        # Email-specific: include subject hint derived from the ask summary
        return {
            "subject_hint": f"Follow-up: {self.entity.ask_summary[:60]}"
        }

    def execute(self) -> dict:
        if self.entity.source_type.value == "email":
            cleaned_content = sanitize_email_body(self.content, self.sender_name)
            logger.info(
                f"Sending Gmail thread reply for follow-up {self.entity.id} "
                f"into thread {self.entity.source_ref}"
            )
            sent = send_reply_to_thread(
                self.entity.source_ref,
                self.entity.created_by_user_id,
                cleaned_content,
                self.entity.ask_summary,
            )
            payload = {
                "draft_body": cleaned_content,
                "target_contact": sent["target_email"],
                "channel": self.entity.channel.value,
                "metadata": {
                    "follow_up_id": str(self.entity.id),
                    "source_ref": self.entity.source_ref,
                    "priority": self.entity.priority.value,
                },
                "gmail_delivery": sent,
            }
            payload.update(self._extra_fields())
            return payload
        return super().execute()


class EmailExecutorGateway:
    @staticmethod
    def send(entity: FollowUpEntity, content: str, sender_name: str = "") -> dict:
        return EmailExecutor(entity, content, sender_name).execute()
