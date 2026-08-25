"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VoteIn(BaseModel):
    game_id: str
    pick: str = Field(..., pattern="^(home|away|draw)$")
    ip: str | None = None


class HealthOut(BaseModel):
    status: str
    db: str
    games: int
    predictions: int
