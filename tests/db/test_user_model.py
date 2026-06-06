import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models import User, UserSettings, UserStorageUsage, UsageLog
from models.enums import KBSourceType, KBStatus


class TestUserModel:
    def test_create_user(self, db_session):
        user = User(
            email="new@example.com",
            supabase_user_id="supabase-new",
            user_type="pro",
            credits_remaining=500,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.user_type == "pro"
        assert user.credits_remaining == 500
        assert user.created_at is not None

    def test_user_email_unique_constraint(self, db_session, user):
        duplicate = User(
            email=user.email,
            supabase_user_id="different-supabase",
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_supabase_id_unique_constraint(self, db_session, user):
        duplicate = User(
            email="different@example.com",
            supabase_user_id=user.supabase_user_id,
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_defaults(self, db_session):
        user = User(email="defaults@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.user_type == "free"
        assert user.credits_remaining == 100
        assert user.last_reset_date is not None

    def test_get_max_credits(self, user, admin_user):
        assert user.get_max_credits() == 999999
        assert admin_user.get_max_credits() == 999999

    def test_user_settings_relationship(self, db_session, user):
        settings = UserSettings(user_id=user.id, widget_theme="dark")
        db_session.add(settings)
        db_session.commit()

        fetched = db_session.get(User, user.id)
        assert fetched.settings is not None
        assert fetched.settings.widget_theme == "dark"

    def test_user_settings_cascade_delete(self, db_session, user):
        settings = UserSettings(user_id=user.id)
        db_session.add(settings)
        db_session.commit()

        db_session.delete(user)
        db_session.commit()

        remaining = db_session.get(UserSettings, settings.id)
        assert remaining is None

    def test_user_storage_usage_relationship(self, db_session, user):
        usage = UserStorageUsage(
            user_id=user.id,
            total_files=5,
            total_size_bytes=1024,
            total_chunks=10,
        )
        db_session.add(usage)
        db_session.commit()

        fetched = db_session.get(User, user.id)
        assert fetched.storage_usage is not None
        assert fetched.storage_usage.total_files == 5

    def test_user_storage_usage_cascade_delete(self, db_session, user):
        usage = UserStorageUsage(user_id=user.id)
        db_session.add(usage)
        db_session.commit()

        db_session.delete(user)
        db_session.commit()

        remaining = db_session.get(UserStorageUsage, user.id)
        assert remaining is None

    def test_user_usage_logs_relationship(self, db_session, user, agent):
        log = UsageLog(
            user_id=user.id,
            agent_id=agent.id,
            credits_used=3,
            message_content="Hello",
            response_content="Hi there",
        )
        db_session.add(log)
        db_session.commit()

        fetched = db_session.get(User, user.id)
        assert len(fetched.usage_logs) == 1
        assert fetched.usage_logs[0].credits_used == 3

    def test_user_agents_relationship(self, db_session, user):
        agent1 = Agent(user_id=user.id, name="Agent 1")
        agent2 = Agent(user_id=user.id, name="Agent 2")
        db_session.add_all([agent1, agent2])
        db_session.commit()

        fetched = db_session.get(User, user.id)
        assert len(fetched.agents) == 2
        assert {a.name for a in fetched.agents} == {"Agent 1", "Agent 2"}

    def test_user_agents_cascade_delete(self, db_session, user, agent):
        db_session.delete(user)
        db_session.commit()

        remaining = db_session.get(Agent, agent.id)
        assert remaining is None


class TestUserSettingsModel:
    def test_create_user_settings(self, db_session, user):
        settings = UserSettings(
            user_id=user.id,
            widget_theme="dark",
            widget_color="#ff0000",
            email_notifications=False,
        )
        db_session.add(settings)
        db_session.commit()
        db_session.refresh(settings)

        assert settings.id is not None
        assert settings.widget_theme == "dark"
        assert settings.widget_color == "#ff0000"
        assert settings.email_notifications is False

    def test_user_settings_defaults(self, db_session, user):
        settings = UserSettings(user_id=user.id)
        db_session.add(settings)
        db_session.commit()
        db_session.refresh(settings)

        assert settings.widget_theme == "default"
        assert settings.widget_color == "#4a6cf7"
        assert settings.widget_position == "bottom-right"
        assert settings.widget_size == "medium"
        assert settings.email_notifications is True
        assert settings.browser_notifications is False
        assert settings.notification_frequency == "immediate"
        assert settings.default_language == "en"
        assert settings.response_style == "professional"
        assert settings.max_response_length == "medium"
        assert settings.auto_suggestions is True
        assert settings.data_retention_days == 30
        assert settings.analytics_enabled is True
        assert settings.share_usage_data is False
        assert settings.api_rate_limit_preference == "standard"
        assert settings.debug_mode is False

    def test_user_settings_one_per_user(self, db_session, user):
        settings1 = UserSettings(user_id=user.id)
        settings2 = UserSettings(user_id=user.id)
        db_session.add_all([settings1, settings2])
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_settings_custom_preferences_json(self, db_session, user):
        settings = UserSettings(
            user_id=user.id,
            custom_preferences={"theme": "custom", "layout": "compact"},
        )
        db_session.add(settings)
        db_session.commit()
        db_session.refresh(settings)

        assert settings.custom_preferences == {"theme": "custom", "layout": "compact"}


class TestUserStorageUsageModel:
    def test_create_storage_usage(self, db_session, user):
        usage = UserStorageUsage(
            user_id=user.id,
            total_files=10,
            total_size_bytes=2048,
            total_chunks=20,
        )
        db_session.add(usage)
        db_session.commit()
        db_session.refresh(usage)

        assert usage.user_id == user.id
        assert usage.total_files == 10
        assert usage.total_size_bytes == 2048
        assert usage.total_chunks == 20

    def test_storage_usage_defaults(self, db_session, user):
        usage = UserStorageUsage(user_id=user.id)
        db_session.add(usage)
        db_session.commit()
        db_session.refresh(usage)

        assert usage.total_files == 0
        assert usage.total_size_bytes == 0
        assert usage.total_chunks == 0

    def test_storage_usage_primary_key_is_user_id(self, db_session, user):
        usage = UserStorageUsage(user_id=user.id)
        db_session.add(usage)
        db_session.commit()

        fetched = db_session.get(UserStorageUsage, user.id)
        assert fetched is not None
        assert fetched.user_id == user.id