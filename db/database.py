from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env file")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL.removeprefix("postgres://")

# Create engine with connection pooling and timeout configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={
        "options": "-c statement_timeout=30000"
    }
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Separate engine + session for background tasks (ingest queue, usage logging, etc.)
_bg_engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("BG_DB_POOL_SIZE", "3")),
    max_overflow=int(os.getenv("BG_DB_MAX_OVERFLOW", "3")),
    pool_timeout=60,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={
        "options": "-c statement_timeout=60000"
    },
)
BackgroundSession = sessionmaker(bind=_bg_engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass
