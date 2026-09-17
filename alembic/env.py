from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your models and database config
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import db modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

load_dotenv()

from db.database import Base
# Import all models so Alembic can detect them
from models import User, Agent, AgentConfig, KnowledgeBase, KBIngestJob, UsageLog, UserSettings, UserStorageUsage, KbChunk, HumanAgent, AgentAssignment, Conversation

config = context.config

# Override sqlalchemy.url with DATABASE_URL from .env
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Handle postgres:// -> postgresql:// conversion
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg2://" + database_url.removeprefix("postgres://")
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata



def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode: emit SQL to stdout, no DBAPI needed."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode: create an engine and bind a connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
