import pytest
from sqlalchemy.exc import IntegrityError

from models import Agent, AgentConfig, KnowledgeBase, WidgetDeployment
from models.enums import KBSourceType, KBStatus


class TestAgentModel:
    def test_create_agent(self, db_session, user):
        agent = Agent(
            user_id=user.id,
            name="Support Bot",
            instructions="Help customers",
            model="groq/llama-3.1-70b",
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.id is not None
        assert agent.user_id == user.id
        assert agent.name == "Support Bot"
        assert agent.instructions == "Help customers"
        assert agent.model == "groq/llama-3.1-70b"
        assert agent.created_at is not None

    def test_agent_default_model(self, db_session, user):
        agent = Agent(user_id=user.id, name="Default Model Agent")
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.model == "groq/openai/gpt-oss-20b"

    def test_agent_user_relationship(self, db_session, user, agent):
        fetched = db_session.get(Agent, agent.id)
        assert fetched.user_id == user.id
        assert fetched.user is not None
        assert fetched.user.email == user.email

    def test_agent_config_relationship(self, db_session, agent):
        config = AgentConfig(
            agent_id=agent.id,
            retrieval_enabled=True,
            retrieval_top_k=10,
            vector_store_namespace="custom-ns",
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.config is not None
        assert agent.config.retrieval_top_k == 10
        assert agent.config.vector_store_namespace == "custom-ns"

    def test_agent_config_cascade_delete(self, db_session, agent_with_config):
        config_id = agent_with_config.config.id
        db_session.delete(agent_with_config)
        db_session.commit()

        remaining = db_session.get(AgentConfig, config_id)
        assert remaining is None

    def test_agent_config_one_per_agent(self, db_session, agent):
        config1 = AgentConfig(agent_id=agent.id)
        config2 = AgentConfig(agent_id=agent.id)
        db_session.add_all([config1, config2])
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_agent_knowledge_bases_relationship(self, db_session, agent):
        kb1 = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.text,
            title="KB 1",
            status=KBStatus.ready,
        )
        kb2 = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.upload_pdf,
            title="KB 2",
            status=KBStatus.pending,
        )
        db_session.add_all([kb1, kb2])
        db_session.commit()

        fetched = db_session.get(Agent, agent.id)
        assert len(fetched.knowledge_bases) == 2
        assert {kb.title for kb in fetched.knowledge_bases} == {"KB 1", "KB 2"}

    def test_agent_knowledge_bases_cascade_delete(self, db_session, agent, knowledge_base):
        kb_id = knowledge_base.id
        db_session.delete(agent)
        db_session.commit()

        remaining = db_session.get(KnowledgeBase, kb_id)
        assert remaining is None

    def test_agent_widget_deployment_relationship(self, db_session, agent):
        deployment = WidgetDeployment(
            agent_id=agent.id,
            display_name="My Widget",
            allowed_domains=["example.com"],
        )
        db_session.add(deployment)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.widget_deployment is not None
        assert agent.widget_deployment.display_name == "My Widget"

    def test_agent_widget_deployment_cascade_delete(self, db_session, agent, widget_deployment):
        dep_id = widget_deployment.id
        db_session.delete(agent)
        db_session.commit()

        remaining = db_session.get(WidgetDeployment, dep_id)
        assert remaining is None


class TestAgentConfigModel:
    def test_create_agent_config(self, db_session, agent):
        config = AgentConfig(
            agent_id=agent.id,
            retrieval_enabled=False,
            retrieval_top_k=3,
            embedding_model="text-embedding-3-small",
            vector_store_namespace="test-ns",
            system_prompt_locked=False,
            widget_theme="dark",
            widget_color="#00ff00",
            widget_position="top-left",
            widget_greeting="Welcome!",
            widget_use_color_header=True,
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.id is not None
        assert config.retrieval_enabled is False
        assert config.retrieval_top_k == 3
        assert config.embedding_model == "text-embedding-3-small"
        assert config.vector_store_namespace == "test-ns"
        assert config.system_prompt_locked is False
        assert config.widget_theme == "dark"
        assert config.widget_color == "#00ff00"
        assert config.widget_position == "top-left"
        assert config.widget_greeting == "Welcome!"
        assert config.widget_use_color_header is True

    def test_agent_config_defaults(self, db_session, agent):
        config = AgentConfig(agent_id=agent.id)
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.retrieval_enabled is True
        assert config.retrieval_top_k == 4
        assert config.embedding_model is None
        assert config.vector_store_namespace is None
        assert config.system_prompt_locked is True
        assert config.widget_theme == "light"
        assert config.widget_color == "#4a6cf7"
        assert config.widget_position == "bottom-right"
        assert config.widget_greeting is None
        assert config.widget_use_color_header is False
        assert config.created_at is not None
        assert config.updated_at is not None

    def test_agent_config_updated_at_on_change(self, db_session, agent_with_config):
        original_updated = agent_with_config.config.updated_at
        agent_with_config.config.retrieval_top_k = 7
        db_session.commit()
        db_session.refresh(agent_with_config.config)

        assert agent_with_config.config.updated_at > original_updated