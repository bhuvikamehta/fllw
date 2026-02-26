import pytest
from datetime import datetime, timedelta
from backend.domain.models import FollowUpEntity, EntityStatus
from backend.infrastructure.scheduler import Scheduler

class MockRepo:
    def __init__(self, entities):
        self.entities = entities
        self.saved = []
    
    def get_by_status(self, statuses):
        return [e for e in self.entities if e.status in statuses]
        
    def save_follow_up(self, entity):
        self.saved.append(entity)
        return entity
        
    def log_event(self, event):
        pass

def test_scheduler_escalation(mock_entity):
    # Setup entity in followed_up_2 state, due now
    mock_entity.status = EntityStatus.followed_up_2
    mock_entity.next_follow_up_at = datetime.utcnow() - timedelta(minutes=1)
    
    repo = MockRepo([mock_entity])
    scheduler = Scheduler(repo=repo)
    
    scheduler.tick()
    
    assert len(repo.saved) == 1
    escalated_entity = repo.saved[0]
    assert escalated_entity.status == EntityStatus.escalated

def test_scheduler_follow_up_1(mock_entity):
    mock_entity.status = EntityStatus.sent
    mock_entity.next_follow_up_at = datetime.utcnow() - timedelta(minutes=1)
    
    repo = MockRepo([mock_entity])
    scheduler = Scheduler(repo=repo)
    
    scheduler.tick()
    
    assert len(repo.saved) == 1
    new_entity = repo.saved[0]
    assert new_entity.status == EntityStatus.followed_up_1
    assert new_entity.attempts_count == 1
