import pytest
from sqlalchemy import select

from models import UsageLog
from models.enums import KBSourceType, KBStatus


class TestUsageLogModel:
    def test_create_usage_log(self, db_session, user, agent):
        log = UsageLog(
            user_id=user.id,
            agent_id=agent.id,
            credits_used=5,
            message_content="How do I reset my password?",
            response_content="Go to settings and click reset.",
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.id is not None
        assert log.user_id == user.id
        assert log.agent_id == agent.id
        assert log.credits_used == 5
        assert log.message_content == "How do I reset my password?"
        assert log.response_content == "Go to settings and click reset."
        assert log.timestamp is not None

    def test_usage_log_defaults(self, db_session, user, agent):
        log = UsageLog(user_id=user.id, agent_id=agent.id)
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.credits_used == 1
        assert log.message_content is None
        assert log.response_content is None

    def test_usage_log_user_relationship(self, db_session, user, agent):
        log = UsageLog(user_id=user.id, agent_id=agent.id)
        db_session.add(log)
        db_session.commit()

        fetched = db_session.get(UsageLog, log.id)
        assert fetched.user_id == user.id
        assert fetched.user is not None
        assert fetched.user.email == user.email

    def test_usage_log_agent_relationship(self, db_session, user, agent):
        log = UsageLog(user_id=user.id, agent_id=agent.id)
        db_session.add(log)
        db_session.commit()

        fetched = db_session.get(UsageLog, log.id)
        assert fetched.agent_id == agent.id
        assert fetched.agent is not None
        assert fetched.agent.name == agent.name

    def test_usage_log_indexes(self, db_session, user, agent):
        logs = [
            UsageLog(user_id=user.id, agent_id=agent.id, credits_used=i)
            for i in range(10)
        ]
        db_session.add_all(logs)
        db_session.commit()

        user_logs = db_session.execute(
            select(UsageLog).where(UsageLog.user_id == user.id)
        ).scalars().all()
        assert len(user_logs) == 10

        agent_logs = db_session.execute(
            select(UsageLog).where(UsageLog.agent_id == agent.id)
        ).scalars().all()
        assert len(agent_logs) == 10

    def test_usage_log_timestamp_ordering(self, db_session, user, agent):
        log1 = UsageLog(user_id=user.id, agent_id=agent.id, credits_used=1)
        db_session.add(log1)
        db_session.commit()

        log2 = UsageLog(user_id=user.id, agent_id=agent.id, credits_used=2)
        db_session.add(log2)
        db_session.commit()

        log3 = UsageLog(user_id=user.id, agent_id=agent.id, credits_used=3)
        db_session.add(log3)
        db_session.commit()

        logs = db_session.execute(
            select(UsageLog)
            .where(UsageLog.user_id == user.id)
            .order_by(UsageLog.timestamp)
        ).scalars().all()

        assert len(logs) == 3
        assert logs[0].credits_used == 1
        assert logs[1].credits_used == 2
        assert logs[2].credits_used == 3