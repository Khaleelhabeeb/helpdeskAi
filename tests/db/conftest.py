import os
import sys
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from db.database import Base
from models import (
    User,
    UsageLog,
    UserSettings,
    UserStorageUsage,
    Agent,
    AgentConfig,
    KnowledgeBase,
    KBIngestJob,
    WidgetDeployment,
    ChatSession,
    ChatMessage,
    KBSourceType,
    KBStatus,
    JobState,
)


@pytest.fixture(scope="session")
def engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    yield session
    session.close()
    connection.close()


@pytest.fixture
def user(db_session: Session) -> User:
    u = User(
        email="test@example.com",
        supabase_user_id="supabase-123",
        user_type="free",
        credits_remaining=100,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def admin_user(db_session: Session) -> User:
    u = User(
        email="admin@example.com",
        supabase_user_id="supabase-admin",
        user_type="admin",
        credits_remaining=999999,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def agent(db_session: Session, user: User) -> Agent:
    a = Agent(user_id=user.id, name="Test Agent", instructions="Be helpful")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture
def agent_with_config(db_session: Session, agent: Agent) -> Agent:
    config = AgentConfig(
        agent_id=agent.id,
        retrieval_enabled=True,
        retrieval_top_k=5,
        vector_store_namespace=f"ns-{agent.id}",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def knowledge_base(db_session: Session, agent: Agent) -> KnowledgeBase:
    kb = KnowledgeBase(
        agent_id=agent.id,
        source_type=KBSourceType.text,
        title="Test KB",
        status=KBStatus.ready,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    return kb


@pytest.fixture
def widget_deployment(db_session: Session, agent: Agent) -> WidgetDeployment:
    wd = WidgetDeployment(
        agent_id=agent.id,
        display_name="Test Widget",
        allowed_domains=["example.com"],
    )
    db_session.add(wd)
    db_session.commit()
    db_session.refresh(wd)
    return wd