import pytest
from sqlalchemy import select, func

from models import (
    User,
    Agent,
    AgentConfig,
    KnowledgeBase,
    KBIngestJob,
    WidgetDeployment,
    ChatSession,
    ChatMessage,
    UsageLog,
    UserSettings,
    UserStorageUsage,
)
from models.enums import KBSourceType, KBStatus, JobState


class TestFullUserAgentFlow:
    def test_user_creates_agent_with_config_and_kb(self, db_session):
        user = User(email="flow@example.com", supabase_user_id="supabase-flow")
        db_session.add(user)
        db_session.commit()

        agent = Agent(user_id=user.id, name="Flow Agent", instructions="Help users")
        db_session.add(agent)
        db_session.commit()

        config = AgentConfig(
            agent_id=agent.id,
            retrieval_enabled=True,
            retrieval_top_k=5,
            vector_store_namespace=f"ns-{agent.id}",
        )
        db_session.add(config)
        db_session.commit()

        kb = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.text,
            title="FAQ",
            status=KBStatus.ready,
        )
        db_session.add(kb)
        db_session.commit()

        job = KBIngestJob(kb_id=kb.id, state=JobState.succeeded, total_chunks=10)
        db_session.add(job)
        db_session.commit()

        agents = db_session.execute(
            select(Agent).where(Agent.user_id == user.id)
        ).scalars().all()
        assert len(agents) == 1
        fetched_agent = agents[0]

        config = db_session.execute(
            select(AgentConfig).where(AgentConfig.agent_id == fetched_agent.id)
        ).scalar_one()
        assert config is not None

        kbs = db_session.execute(
            select(KnowledgeBase).where(KnowledgeBase.agent_id == fetched_agent.id)
        ).scalars().all()
        assert len(kbs) == 1

        jobs = db_session.execute(
            select(KBIngestJob).where(KBIngestJob.kb_id == kbs[0].id)
        ).scalars().all()
        assert jobs[0].state == JobState.succeeded

    def test_user_settings_and_storage_usage(self, db_session):
        user = User(email="settings@example.com", supabase_user_id="supabase-settings")
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            widget_theme="dark",
            email_notifications=False,
        )
        storage = UserStorageUsage(
            user_id=user.id,
            total_files=5,
            total_size_bytes=5120,
            total_chunks=25,
        )
        db_session.add_all([settings, storage])
        db_session.commit()

        fetched_settings = db_session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        ).scalar_one()
        assert fetched_settings.widget_theme == "dark"

        fetched_storage = db_session.get(UserStorageUsage, user.id)
        assert fetched_storage.total_files == 5

    def test_widget_deployment_with_chat_sessions(self, db_session, user):
        agent = Agent(user_id=user.id, name="Widget Agent")
        db_session.add(agent)
        db_session.commit()

        deployment = WidgetDeployment(
            agent_id=agent.id,
            display_name="Chat Widget",
            allowed_domains=["app.example.com"],
        )
        db_session.add(deployment)
        db_session.commit()

        session = ChatSession(
            deployment_id=deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-123",
        )
        db_session.add(session)
        db_session.commit()

        messages = [
            ChatMessage(session_id=session.id, role="user", content="Hello"),
            ChatMessage(session_id=session.id, role="assistant", content="Hi!"),
            ChatMessage(session_id=session.id, role="user", content="Help me"),
        ]
        db_session.add_all(messages)
        db_session.commit()

        sessions = db_session.execute(
            select(ChatSession).where(ChatSession.deployment_id == deployment.id)
        ).scalars().all()
        assert len(sessions) == 1

        msgs = db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sessions[0].id)
        ).scalars().all()
        assert len(msgs) == 3


class TestUsageTracking:
    def test_usage_logs_link_user_and_agent(self, db_session):
        user = User(email="usage@example.com", supabase_user_id="supabase-usage")
        agent = Agent(user_id=user.id, name="Usage Agent")
        db_session.add_all([user, agent])
        db_session.commit()

        logs = [
            UsageLog(user_id=user.id, agent_id=agent.id, credits_used=2),
            UsageLog(user_id=user.id, agent_id=agent.id, credits_used=3),
        ]
        db_session.add_all(logs)
        db_session.commit()

        user_logs = db_session.execute(
            select(UsageLog).where(UsageLog.user_id == user.id)
        ).scalars().all()
        assert len(user_logs) == 2
        assert sum(l.credits_used for l in user_logs) == 5

        agent_logs = db_session.execute(
            select(UsageLog).where(UsageLog.agent_id == agent.id)
        ).scalars().all()
        assert len(agent_logs) == 2

    def test_multiple_agents_per_user_usage_isolation(self, db_session):
        user = User(email="multi@example.com", supabase_user_id="supabase-multi")
        agent1 = Agent(user_id=user.id, name="Agent 1")
        agent2 = Agent(user_id=user.id, name="Agent 2")
        db_session.add_all([user, agent1, agent2])
        db_session.commit()

        log1 = UsageLog(user_id=user.id, agent_id=agent1.id, credits_used=5)
        log2 = UsageLog(user_id=user.id, agent_id=agent2.id, credits_used=3)
        db_session.add_all([log1, log2])
        db_session.commit()

        a1_logs = db_session.execute(
            select(UsageLog).where(UsageLog.agent_id == agent1.id)
        ).scalars().all()
        assert len(a1_logs) == 1
        assert a1_logs[0].credits_used == 5

        a2_logs = db_session.execute(
            select(UsageLog).where(UsageLog.agent_id == agent2.id)
        ).scalars().all()
        assert len(a2_logs) == 1
        assert a2_logs[0].credits_used == 3


class TestCascadeDeletes:
    def test_delete_agent_cascades_to_related(self, db_session, user):
        agent = Agent(user_id=user.id, name="Cascade Agent")
        db_session.add(agent)
        db_session.commit()

        config = AgentConfig(agent_id=agent.id)
        kb = KnowledgeBase(agent_id=agent.id, source_type=KBSourceType.text)
        db_session.add_all([config, kb])
        db_session.flush()

        job = KBIngestJob(kb_id=kb.id, state=JobState.queued)
        deployment = WidgetDeployment(agent_id=agent.id, display_name="Widget")
        db_session.add_all([job, deployment])
        db_session.flush()

        session = ChatSession(deployment_id=deployment.id, agent_id=agent.id, visitor_hash="v1")
        db_session.add(session)
        db_session.flush()

        message = ChatMessage(session_id=session.id, role="user", content="test")
        db_session.add(message)
        db_session.commit()

        db_session.delete(agent)
        db_session.commit()

        assert db_session.get(Agent, agent.id) is None
        assert db_session.get(AgentConfig, config.id) is None
        assert db_session.get(KnowledgeBase, kb.id) is None
        assert db_session.get(KBIngestJob, job.id) is None
        assert db_session.get(WidgetDeployment, deployment.id) is None
        assert db_session.get(ChatSession, session.id) is None
        assert db_session.get(ChatMessage, message.id) is None


class TestComplexQueries:
    def test_agents_with_ready_knowledge_bases(self, db_session, user):
        agent1 = Agent(user_id=user.id, name="Ready KB Agent")
        agent2 = Agent(user_id=user.id, name="Pending KB Agent")
        db_session.add_all([agent1, agent2])
        db_session.commit()

        kb1 = KnowledgeBase(agent_id=agent1.id, source_type=KBSourceType.text, status=KBStatus.ready)
        kb2 = KnowledgeBase(agent_id=agent1.id, source_type=KBSourceType.text, status=KBStatus.ready)
        kb3 = KnowledgeBase(agent_id=agent2.id, source_type=KBSourceType.text, status=KBStatus.pending)
        db_session.add_all([kb1, kb2, kb3])
        db_session.commit()

        agents_with_ready = db_session.execute(
            select(Agent)
            .join(KnowledgeBase)
            .where(KnowledgeBase.status == KBStatus.ready)
            .distinct()
        ).scalars().all()

        assert len(agents_with_ready) == 1
        assert agents_with_ready[0].id == agent1.id

    def test_users_with_agents_and_usage(self, db_session):
        user1 = User(email="u1@example.com", supabase_user_id="s1")
        user2 = User(email="u2@example.com", supabase_user_id="s2")
        db_session.add_all([user1, user2])
        db_session.commit()

        agent1 = Agent(user_id=user1.id, name="Agent 1")
        agent2 = Agent(user_id=user1.id, name="Agent 2")
        agent3 = Agent(user_id=user2.id, name="Agent 3")
        db_session.add_all([agent1, agent2, agent3])
        db_session.commit()

        db_session.add_all([
            UsageLog(user_id=user1.id, agent_id=agent1.id, credits_used=5),
            UsageLog(user_id=user1.id, agent_id=agent2.id, credits_used=3),
            UsageLog(user_id=user2.id, agent_id=agent3.id, credits_used=10),
        ])
        db_session.commit()

        user_usage = db_session.execute(
            select(
                User.email,
                func.count(UsageLog.id).label("log_count"),
                func.sum(UsageLog.credits_used).label("total_credits")
            )
            .join(UsageLog, User.id == UsageLog.user_id)
            .group_by(User.id)
        ).all()

        assert len(user_usage) == 2
        u1_data = next(u for u in user_usage if u.email == "u1@example.com")
        assert u1_data.log_count == 2
        assert u1_data.total_credits == 8

        u2_data = next(u for u in user_usage if u.email == "u2@example.com")
        assert u2_data.log_count == 1
        assert u2_data.total_credits == 10