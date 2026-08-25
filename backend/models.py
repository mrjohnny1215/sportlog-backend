"""SQLAlchemy ORM models for the Sports AI platform."""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(32), primary_key=True)  # e.g. "KBO:LT"
    sport = Column(String(16), nullable=False)
    league = Column(String(16), nullable=False)
    name = Column(String(64), nullable=False)
    short = Column(String(8), nullable=True)
    color = Column(String(8), nullable=True)


class Venue(Base):
    __tablename__ = "venues"

    id = Column(String(32), primary_key=True)
    name = Column(String(128), nullable=False)
    sport = Column(String(16), nullable=False)
    city = Column(String(64), nullable=True)
    is_dome = Column(Boolean, default=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)


class Game(Base):
    __tablename__ = "games"

    id = Column(String(48), primary_key=True)
    sport = Column(String(16), nullable=False)
    league = Column(String(16), nullable=False)
    game_datetime = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), default="scheduled")  # scheduled|live|final|cancelled|postponed
    home_team_id = Column(String(32), nullable=False)
    away_team_id = Column(String(32), nullable=False)
    home_team_name = Column(String(64), nullable=False)
    away_team_name = Column(String(64), nullable=False)
    venue_id = Column(String(32), nullable=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    # baseball starter pitchers / hockey starting goalies
    home_starter = Column(String(64), nullable=True)
    away_starter = Column(String(64), nullable=True)
    home_starter_era = Column(Float, nullable=True)
    away_starter_era = Column(Float, nullable=True)
    is_dome = Column(Boolean, default=False)
    weather_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class GameLog(Base):
    __tablename__ = "game_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sport = Column(String(16), nullable=False)
    league = Column(String(16), nullable=False)
    game_date = Column(Date, nullable=False)
    home_team_id = Column(String(32), nullable=False)
    away_team_id = Column(String(32), nullable=False)
    home_team_name = Column(String(64), nullable=False)
    away_team_name = Column(String(64), nullable=False)
    home_score = Column(Integer, nullable=False)
    away_score = Column(Integer, nullable=False)
    venue_id = Column(String(32), nullable=True)
    details_json = Column(JSON, nullable=True)
    source = Column(String(32), default="seed")

    __table_args__ = (
        Index("ix_gamelog_sport_league_date", "sport", "league", "game_date"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(48), unique=True, nullable=False, index=True)
    sport = Column(String(16), nullable=False)
    league = Column(String(16), nullable=False)

    # Moneyline
    ml_home_pct = Column(Float, nullable=False)
    ml_draw_pct = Column(Float, nullable=True)
    ml_away_pct = Column(Float, nullable=False)
    ml_pick = Column(String(8), nullable=False)  # home|away|draw

    # Handicap / Spread
    hc_line = Column(Float, nullable=False)
    hc_pick = Column(String(8), nullable=False)  # home|away
    hc_cover_pct = Column(Float, nullable=False)

    # Totals (Over/Under)
    tot_line = Column(Float, nullable=False)
    tot_pick = Column(String(8), nullable=False)  # over|under
    tot_pct = Column(Float, nullable=False)

    # Baseball 1st-inning (NRFI / YRFI)
    nrfi_pct = Column(Float, nullable=True)
    yrfi_pct = Column(Float, nullable=True)
    nrfi_pick = Column(String(8), nullable=True)  # NRFI|YRFI

    # Meta
    value_bet = Column(Boolean, default=False)
    value_bet_detail = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False)
    ai_summary = Column(Text, nullable=True)

    # Resolution (filled by the daily settle job)
    resolved = Column(Boolean, default=False)
    ml_correct = Column(Boolean, nullable=True)
    hc_correct = Column(Boolean, nullable=True)
    tot_correct = Column(Boolean, nullable=True)
    nrfi_correct = Column(Boolean, nullable=True)

    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(48), nullable=False, index=True)
    pick = Column(String(8), nullable=False)  # home|away|draw
    ip_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True))
