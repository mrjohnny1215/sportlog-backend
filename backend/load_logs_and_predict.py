"""Bulk-load 180d naver_logs into game_logs and re-run AI predictions.

1. Insert every record from naver_logs_180.json into game_logs, mapping
   home->home_team_id/home_team_name and away->away_team_id/away_team_name
   (NOT NULL compliant). Safe bulk insert via a natural-key unique index +
   ON CONFLICT DO NOTHING so re-runs never duplicate.
2. Call ai.predictor.predict_game(db, game) for EVERY scheduled game and
   upsert the result into predictions (recompute = overwrite existing rows).
3. Print final counts to stdout for verification.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

# Make the backend package importable regardless of cwd.
BACKEND = "/opt/data/sports/backend"
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import SessionLocal, engine
from models import GameLog, Game, Prediction
import config
from ai import predictor

JSON_PATH = "/opt/data/profiles/sports/attachments/naver_logs_180.json"
NATURAL_KEY = ["sport", "league", "game_date", "home_team_id", "away_team_id"]


def load_logs(db):
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for r in data:
        rows.append(
            {
                "sport": r.get("sport", "etc"),
                "league": r.get("league", "etc"),
                "game_date": datetime.strptime(r["game_date"], "%Y-%m-%d").date(),
                "home_team_id": r["home"],
                "away_team_id": r["away"],
                "home_team_name": r["home"],
                "away_team_name": r["away"],
                "home_score": int(r["home_score"]),
                "away_score": int(r["away_score"]),
                "venue_id": r.get("venue"),
                "source": "naver_logs_180",
            }
        )

    # --- Step 0: clean pre-existing seed duplicates -----------------------
    # The seed generator occasionally inserted the same natural key twice.
    # Collapse every duplicate group down to a single row (keep lowest id)
    # so the unique index below can be created and ON CONFLICT can work.
    dup_groups = db.execute(
        text(
            "SELECT COUNT(*) FROM ("
            "SELECT sport, league, game_date, home_team_id, away_team_id "
            "FROM game_logs GROUP BY 1,2,3,4,5 HAVING COUNT(*) > 1)"
        )
    ).scalar()
    if dup_groups:
        db.execute(
            text(
                "DELETE FROM game_logs WHERE id NOT IN ("
                "SELECT MIN(id) FROM game_logs "
                "GROUP BY sport, league, game_date, home_team_id, away_team_id)"
            )
        )
        db.commit()
        print(f"    [cleanup] 기존 중복 그룹 {dup_groups}개 정리 완료 "
              f"(각 그룹 1행 잔류)")

    # --- Step 1: natural-key unique index for ON CONFLICT DO NOTHING ------
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_gamelog_natural "
                "ON game_logs(sport, league, game_date, home_team_id, away_team_id)"
            )
        )

    # --- Step 2: safe bulk insert (idempotent) ----------------------------
    stmt = sqlite_insert(GameLog.__table__).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=NATURAL_KEY)
    db.execute(stmt)
    db.commit()
    return len(rows)


def recompute_predictions(db):
    now = datetime.now(config.KST)
    games = db.query(Game).filter(Game.status == "scheduled").all()
    updated = 0
    for g in games:
        data = predictor.predict_game(db, g)
        existing = (
            db.query(Prediction).filter(Prediction.game_id == g.id).first()
        )
        if existing:
            for k, v in data.items():
                if k == "game_id":
                    continue
                setattr(existing, k, v)
            existing.updated_at = now
        else:
            db.add(Prediction(**data, created_at=now, updated_at=now))
        updated += 1
    db.commit()
    return updated


def main():
    db = SessionLocal()
    try:
        inserted = load_logs(db)
        total_logs = db.query(GameLog).count()

        updated = recompute_predictions(db)
        total_preds = db.query(Prediction).count()
    finally:
        db.close()

    print("=" * 56)
    print("[1] game_logs 적재 완료")
    print(f"    이번 run 삽입 시도: {inserted}건")
    print(f"    game_logs 총 건수 : {total_logs}건")
    print("-" * 56)
    print("[2] AI 예측 재연산 완료 (predict_game 호출)")
    print(f"    갱신된 예정 경기 수 : {updated}건")
    print(f"    predictions 총 건수: {total_preds}건")
    print("=" * 56)


if __name__ == "__main__":
    main()
