from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
    poolclass=QueuePool,
    pool_pre_ping=True,
    pool_timeout=20,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, bind=engine, autoflush=False)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close
