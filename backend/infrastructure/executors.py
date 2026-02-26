import logging
from ..domain.models import FollowUpEntity

logger = logging.getLogger(__name__)

class EmailExecutorGateway:
    @staticmethod
    def send(entity: FollowUpEntity, content: str):
        """
        Mock executor for Email.
        """
        logger.info(f"Sending EMAIL to {entity.target_contact} for follow-up {entity.id}\nContent: {content}")
        return True

class SlackExecutorGateway:
    @staticmethod
    def send(entity: FollowUpEntity, content: str):
        """
        Mock executor for Slack.
        """
        logger.info(f"Sending SLACK to {entity.target_contact} for follow-up {entity.id}\nContent: {content}")
        return True
