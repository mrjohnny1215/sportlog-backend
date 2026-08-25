"""SQLAlchemy engine, session factory and base for the Sports AI platform."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Models are imported lazily to avoid circular imports."""
    from models import Team, Venue, Game, GameLog, Prediction, Vote  # noqa: F401

    Base.metadata.create_all(bind=engine)
