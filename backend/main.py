"""FastAPI application — REST API for the Stadium Scoreboard platform.

Endpoints
--------
  GET  /api/health                      liveness + counts
  GET  /api/games?date=&sport=          scoreboard match cards (with predictions)
  GET  /api/predictions/:game_id        single prediction detail + H2H + momentum
  GET  /api/parlay/today                today's 2-3 leg combo
  GET  /api/hitrate?period=&sport=      line-by-line hit-rate dashboard
  POST /api/vote                        one-click user vote (IP hashed)
  GET  /api/votes/:game_id              aggregated vote shares
  POST /api/admin/seed                  (re)seed deterministic demo data
  POST /api/admin/run-predictions       force predictions for upcoming games
"""
from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

# Load .env (DATABASE_URL, SEED_ENABLED, etc.) before importing config/database
# so both local SQLite dev runs and Docker/Postgres prod run from the same code.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional in some deployments
    pass

import config
from database import SessionLocal, init_db
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # First-boot seed so the board is never empty.
    db = SessionLocal()
    try:
        from models import Game, GameLog

        if db.query(GameLog).count() == 0:
            from crawler import seed_data

            seed_data.seed_teams(db)
            seed_data.generate_game_logs(db, days=30)
            seed_data.generate_today_games(db, horizon_days=2)
            log.info("first-boot seed complete")
        if db.query(Game).filter(Game.status == "scheduled").count() == 0:
            from crawler import seed_data

            seed_data.generate_today_games(db, horizon_days=2)
        # generate predictions for soonest games
        from crawler.naver_sports import crawl_all_today
        from ai import predictor

        crawl_all_today(db, horizon_days=2)
        _ensure_predictions()
    finally:
        db.close()
    if config.SEED_ENABLED:
        pass
    from scheduler import jobs

    jobs.start()
    yield
    jobs.shutdown()


def _ensure_predictions() -> int:
    from models import Game, Prediction
    from ai import predictor

    db = SessionLocal()
    now = datetime.now(config.KST)
    made = 0
    try:
        due = (
            db.query(Game)
            .filter(Game.status == "scheduled")
            .filter(Game.game_datetime >= now)
            .filter(Game.game_datetime <= now + timedelta(hours=48))
            .all()
        )
        for g in due:
            if db.query(Prediction).filter(Prediction.game_id == g.id).first():
                continue
            data = predictor.predict_game(db, g)
            db.add(Prediction(**data, created_at=now, updated_at=now))
            made += 1
        db.commit()
    finally:
        db.close()
    return made


app = FastAPI(title="Sports AI Scoreboard API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _serialize_game(g, pred=None):
    return {
        "id": g.id,
        "sport": g.sport,
        "league": g.league,
        "game_datetime": g.game_datetime.isoformat() if g.game_datetime else None,
        "status": g.status,
        "home_team_id": g.home_team_id,
        "away_team_id": g.away_team_id,
        "home_team_name": g.home_team_name,
        "away_team_name": g.away_team_name,
        "venue_id": g.venue_id,
        "home_score": g.home_score,
        "away_score": g.away_score,
        "home_starter": g.home_starter,
        "away_starter": g.away_starter,
        "home_starter_era": g.home_starter_era,
        "away_starter_era": g.away_starter_era,
        "is_dome": g.is_dome,
        "prediction": _serialize_pred(pred) if pred else None,
    }


def _serialize_pred(p):
    return {
        "ml_home_pct": p.ml_home_pct,
        "ml_draw_pct": p.ml_draw_pct,
        "ml_away_pct": p.ml_away_pct,
        "ml_pick": p.ml_pick,
        "hc_line": p.hc_line,
        "hc_pick": p.hc_pick,
        "hc_cover_pct": p.hc_cover_pct,
        "tot_line": p.tot_line,
        "tot_pick": p.tot_pick,
        "tot_pct": p.tot_pct,
        "nrfi_pct": p.nrfi_pct,
        "yrfi_pct": p.yrfi_pct,
        "nrfi_pick": p.nrfi_pick,
        "value_bet": p.value_bet,
        "value_bet_detail": p.value_bet_detail,
        "confidence": p.confidence,
        "ai_summary": p.ai_summary,
        "resolved": p.resolved,
        "ml_correct": p.ml_correct,
        "hc_correct": p.hc_correct,
        "tot_correct": p.tot_correct,
        "nrfi_correct": p.nrfi_correct,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    db = SessionLocal()
    try:
        from models import Game, Prediction

        return {
            "status": "ok",
            "db": "up",
            "games": db.query(Game).count(),
            "predictions": db.query(Prediction).count(),
            "tz": config.TIMEZONE,
        }
    finally:
        db.close()


@app.get("/api/games")
def games(
    date: str | None = Query(None, description="YYYY-MM-DD (KST)"),
    sport: str | None = Query(None),
    league: str | None = Query(None),
):
    from models import Game, Prediction

    db = SessionLocal()
    try:
        q = db.query(Game)
        if sport:
            q = q.filter(Game.sport == sport)
        if league:
            q = q.filter(Game.league == league)
        if date:
            try:
                d = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "bad date format")
            start = datetime(d.year, d.month, d.day, tzinfo=config.KST)
            end = start + timedelta(days=1)
            q = q.filter(Game.game_datetime >= start, Game.game_datetime < end)
        rows = q.order_by(Game.game_datetime).all()
        out = []
        for g in rows:
            pred = db.query(Prediction).filter(Prediction.game_id == g.id).first()
            out.append(_serialize_game(g, pred))
        return {"count": len(out), "games": out}
    finally:
        db.close()


@app.get("/api/predictions/{game_id}")
def prediction_detail(game_id: str):
    from models import Game, Prediction, GameLog

    db = SessionLocal()
    try:
        g = db.query(Game).filter(Game.id == game_id).first()
        if not g:
            raise HTTPException(404, "game not found")
        pred = db.query(Prediction).filter(Prediction.game_id == game_id).first()
        # H2H (last 10 mutually)
        cutoff = datetime.now(config.KST).date() - timedelta(days=30)
        h2h = (
            db.query(GameLog)
            .filter(GameLog.game_date >= cutoff, GameLog.sport == g.sport)
            .all()
        )
        h_w = a_w = d = 0
        for row in h2h:
            if {row.home_team_id, row.away_team_id} == {g.home_team_id, g.away_team_id}:
                if row.home_team_id == g.home_team_id:
                    if row.home_score > row.away_score:
                        h_w += 1
                    elif row.home_score < row.away_score:
                        a_w += 1
                    else:
                        d += 1
                else:
                    if row.away_score > row.home_score:
                        h_w += 1
                    elif row.away_score < row.home_score:
                        a_w += 1
                    else:
                        d += 1
        # momentum: last 5 combined scores for each team
        def momentum(tid):
            vals = [r for r in h2h if r.home_team_id == tid or r.away_team_id == tid][-5:]
            return [
                (r.home_score if r.home_team_id == tid else r.away_score) for r in vals
            ]

        return {
            "game": _serialize_game(g, pred),
            "h2h": {"home_wins": h_w, "away_wins": a_w, "draws": d, "games": h_w + a_w + d},
            "momentum": {
                "home": momentum(g.home_team_id),
                "away": momentum(g.away_team_id),
            },
        }
    finally:
        db.close()


@app.get("/api/parlay/today")
def parlay_today():
    from ai import predictor

    db = SessionLocal()
    try:
        return predictor.build_parlay(db, min_conf=65.0, max_legs=3) or {"legs": [], "combined_confidence": 0}
    finally:
        db.close()


@app.get("/api/upcoming")
def upcoming(days: int = Query(7, ge=1, le=14)):
    from models import Game, Prediction

    db = SessionLocal()
    try:
        now = datetime.now(config.KST)
        end = now + timedelta(days=days)
        rows = (
            db.query(Game)
            .filter(Game.status == "scheduled")
            .filter(Game.game_datetime >= now, Game.game_datetime < end)
            .order_by(Game.game_datetime, Game.id)
            .all()
        )
        out = []
        for g in rows:
            pred = db.query(Prediction).filter(Prediction.game_id == g.id).first()
            out.append(_serialize_game(g, pred))
        return {"count": len(out), "days": days, "games": out}
    finally:
        db.close()


@app.get("/api/hitrate")
def hitrate(
    period: str = Query("30d", pattern="^(all|30d|7d)$"),
    sport: str | None = Query(None),
    league: str | None = Query(None),
):
    from models import Prediction

    db = SessionLocal()
    try:
        q = db.query(Prediction).filter(Prediction.resolved == True)  # noqa: E712
        if sport:
            q = q.filter(Prediction.sport == sport)
        if league:
            q = q.filter(Prediction.league == league)
        if period == "30d":
            cutoff = datetime.now(config.KST) - timedelta(days=30)
            q = q.filter(Prediction.updated_at >= cutoff)
        elif period == "7d":
            cutoff = datetime.now(config.KST) - timedelta(days=7)
            q = q.filter(Prediction.updated_at >= cutoff)
        preds = q.all()

        def rate(field):
            vals = [getattr(p, field) for p in preds if getattr(p, field) is not None]
            if not vals:
                return None
            return round(sum(1 for v in vals if v) / len(vals) * 100, 1)

        lines = {
            "moneyline": rate("ml_correct"),
            "handicap": rate("hc_correct"),
            "totals": rate("tot_correct"),
            "nrfi": rate("nrfi_correct"),
        }
        return {
            "period": period,
            "samples": len(preds),
            "lines": lines,
            "overall": round(
                sum(v for v in lines.values() if v is not None)
                / max(1, len([v for v in lines.values() if v is not None])), 1
            ) if any(lines.values()) else None,
        }
    finally:
        db.close()


class VoteIn(BaseModel):
    game_id: str
    pick: str  # home|away|draw
    ip: str | None = None


@app.post("/api/vote")
def vote(body: VoteIn):
    from models import Vote

    if body.pick not in ("home", "away", "draw"):
        raise HTTPException(400, "pick must be home|away|draw")
    ip = body.ip or "0.0.0.0"
    db = SessionLocal()
    try:
        db.add(Vote(game_id=body.game_id, pick=body.pick, ip_hash=_hash_ip(ip),
                    created_at=datetime.now(config.KST)))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/api/votes/{game_id}")
def votes(game_id: str):
    from models import Vote

    db = SessionLocal()
    try:
        rows = db.query(Vote).filter(Vote.game_id == game_id).all()
        total = len(rows) or 1
        counts = {"home": 0, "away": 0, "draw": 0}
        for r in rows:
            counts[r.pick] = counts.get(r.pick, 0) + 1
        return {
            "total": len(rows),
            "home_pct": round(counts["home"] / total * 100, 1),
            "away_pct": round(counts["away"] / total * 100, 1),
            "draw_pct": round(counts["draw"] / total * 100, 1),
        }
    finally:
        db.close()


@app.post("/api/admin/seed")
def admin_seed():
    from crawler import seed_data

    db = SessionLocal()
    try:
        seed_data.seed_teams(db)
        n_logs = seed_data.generate_game_logs(db, days=30)
        n_games = seed_data.generate_today_games(db, horizon_days=2)
        return {"teams_ok": True, "logs": n_logs, "games": n_games}
    finally:
        db.close()


@app.post("/api/admin/run-predictions")
def admin_run_predictions():
    made = _ensure_predictions()
    return {"generated": made}
