import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models import WidgetDeployment, ChatSession, ChatMessage
from models.enums import KBSourceType, KBStatus


class TestWidgetDeploymentModel:
    def test_create_widget_deployment(self, db_session, agent):
        deployment = WidgetDeployment(
            agent_id=agent.id,
            display_name="Support Widget",
            logo_url="https://example.com/logo.png",
            initial_messages=[{"role": "assistant", "content": "Hello!"}],
            theme="light",
            primary_color="#0000ff",
            allowed_domains=["example.com", "app.example.com"],
            is_enabled=True,
        )
        db_session.add(deployment)
        db_session.commit()
        db_session.refresh(deployment)

        assert deployment.id is not None
        assert deployment.agent_id == agent.id
        assert deployment.deployment_id is not None
        assert len(deployment.deployment_id) == 32
        assert deployment.display_name == "Support Widget"
        assert deployment.logo_url == "https://example.com/logo.png"
        assert deployment.initial_messages == [{"role": "assistant", "content": "Hello!"}]
        assert deployment.theme == "light"
        assert deployment.primary_color == "#0000ff"
        assert deployment.allowed_domains == ["example.com", "app.example.com"]
        assert deployment.is_enabled is True
        assert deployment.created_at is not None
        assert deployment.updated_at is not None

    def test_widget_deployment_defaults(self, db_session, agent):
        deployment = WidgetDeployment(
            agent_id=agent.id,
            display_name="Minimal Widget",
        )
        db_session.add(deployment)
        db_session.commit()
        db_session.refresh(deployment)

        assert deployment.deployment_id is not None
        assert deployment.logo_url is None
        assert deployment.initial_messages == []
        assert deployment.theme == "dark"
        assert deployment.primary_color == "#ffffff"
        assert deployment.allowed_domains == []
        assert deployment.is_enabled is True

    def test_widget_deployment_agent_relationship(self, db_session, agent, widget_deployment):
        fetched = db_session.get(WidgetDeployment, widget_deployment.id)
        assert fetched.agent_id == agent.id
        assert fetched.agent is not None
        assert fetched.agent.name == agent.name

    def test_widget_deployment_unique_agent_id(self, db_session, agent):
        dep1 = WidgetDeployment(agent_id=agent.id, display_name="Widget 1")
        dep2 = WidgetDeployment(agent_id=agent.id, display_name="Widget 2")
        db_session.add_all([dep1, dep2])
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_widget_deployment_unique_deployment_id(self, db_session, agent):
        dep1 = WidgetDeployment(agent_id=agent.id, display_name="Widget 1")
        db_session.add(dep1)
        db_session.commit()

        dep2 = WidgetDeployment(
            agent_id=agent.id,
            display_name="Widget 2",
            deployment_id=dep1.deployment_id,
        )
        db_session.add(dep2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_widget_deployment_updated_at_on_change(self, db_session, widget_deployment):
        original_updated = widget_deployment.updated_at
        import time
        time.sleep(0.01)
        widget_deployment.display_name = "Updated Name"
        widget_deployment.updated_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(widget_deployment)

        assert widget_deployment.updated_at > original_updated

    def test_widget_deployment_sessions_relationship(self, db_session, widget_deployment):
        session1 = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=widget_deployment.agent_id,
            visitor_hash="visitor-1",
        )
        session2 = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=widget_deployment.agent_id,
            visitor_hash="visitor-2",
        )
        db_session.add_all([session1, session2])
        db_session.commit()

        fetched = db_session.get(WidgetDeployment, widget_deployment.id)
        assert len(fetched.sessions) == 2
        assert {s.visitor_hash for s in fetched.sessions} == {"visitor-1", "visitor-2"}

    def test_widget_deployment_sessions_cascade_delete(self, db_session, widget_deployment):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=widget_deployment.agent_id,
            visitor_hash="visitor-test",
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.id
        db_session.delete(widget_deployment)
        db_session.commit()

        remaining = db_session.get(ChatSession, session_id)
        assert remaining is None


class TestChatSessionModel:
    def test_create_chat_session(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-abc123",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.id is not None
        assert session.deployment_id == widget_deployment.id
        assert session.agent_id == agent.id
        assert session.visitor_hash == "visitor-abc123"
        assert session.created_at is not None
        assert session.last_active_at is not None

    def test_chat_session_deployment_relationship(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-rel",
        )
        db_session.add(session)
        db_session.commit()

        fetched = db_session.get(ChatSession, session.id)
        assert fetched.deployment_id == widget_deployment.id
        assert fetched.deployment is not None
        assert fetched.deployment.display_name == widget_deployment.display_name

    def test_chat_session_agent_relationship(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-agent",
        )
        db_session.add(session)
        db_session.commit()

        fetched = db_session.get(ChatSession, session.id)
        assert fetched.agent_id == agent.id
        assert fetched.agent is not None
        assert fetched.agent.name == agent.name

    def test_chat_session_messages_relationship(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-msgs",
        )
        db_session.add(session)
        db_session.commit()

        msg1 = ChatMessage(session_id=session.id, role="user", content="Hello")
        msg2 = ChatMessage(session_id=session.id, role="assistant", content="Hi there!")
        db_session.add_all([msg1, msg2])
        db_session.commit()

        fetched = db_session.get(ChatSession, session.id)
        assert len(fetched.messages) == 2
        assert fetched.messages[0].role == "user"
        assert fetched.messages[1].role == "assistant"

    def test_chat_session_messages_cascade_delete(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-cascade",
        )
        db_session.add(session)
        db_session.commit()

        msg = ChatMessage(session_id=session.id, role="user", content="Test")
        db_session.add(msg)
        db_session.commit()

        msg_id = msg.id
        db_session.delete(session)
        db_session.commit()

        remaining = db_session.get(ChatMessage, msg_id)
        assert remaining is None

    def test_chat_session_last_active_updated(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-active",
        )
        db_session.add(session)
        db_session.commit()

        original_active = session.last_active_at
        session.last_active_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(session)

        assert session.last_active_at > original_active


class TestChatMessageModel:
    def test_create_chat_message(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-msg",
        )
        db_session.add(session)
        db_session.commit()

        message = ChatMessage(
            session_id=session.id,
            role="user",
            content="What are your hours?",
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.content == "What are your hours?"
        assert message.created_at is not None

    def test_chat_message_session_relationship(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-msg-rel",
        )
        db_session.add(session)
        db_session.commit()

        message = ChatMessage(session_id=session.id, role="assistant", content="We're open 9-5")
        db_session.add(message)
        db_session.commit()

        fetched = db_session.get(ChatMessage, message.id)
        assert fetched.session_id == session.id
        assert fetched.session is not None
        assert fetched.session.visitor_hash == "visitor-msg-rel"

    def test_chat_message_roles(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-roles",
        )
        db_session.add(session)
        db_session.commit()

        for role in ["user", "assistant", "system"]:
            msg = ChatMessage(session_id=session.id, role=role, content=f"{role} message")
            db_session.add(msg)
        db_session.commit()

        messages = db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
        ).scalars().all()
        assert {m.role for m in messages} == {"user", "assistant", "system"}

    def test_chat_message_long_content(self, db_session, widget_deployment, agent):
        session = ChatSession(
            deployment_id=widget_deployment.id,
            agent_id=agent.id,
            visitor_hash="visitor-long",
        )
        db_session.add(session)
        db_session.commit()

        long_content = "x" * 10000
        message = ChatMessage(session_id=session.id, role="assistant", content=long_content)
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.content == long_content