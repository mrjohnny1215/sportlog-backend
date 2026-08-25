"""APScheduler cron jobs.

Jobs (all Korea-local times via the KST-aware trigger):
  * ``crawl_30d``    - nightly 03:10 : refresh the 30-day GameLog pool + upcoming games
  * ``predict_3h``   - every 30 min  : for games starting within 3h with no prediction, build one
  * ``settle_08``    - daily 08:05    : grade yesterday's predictions vs final scores, update hit-rate

The scheduler is started from ``main.py`` (lifespan) so it runs inside the
single FastAPI process; under Docker this is the backend container.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import SessionLocal

log = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def crawl_30d_job() -> None:
    from crawler.naver_sports import fetch_30d_logs, crawl_all_today
    from ai import predictor

    db = SessionLocal()
    try:
        n_logs = fetch_30d_logs(db, days=30)
        res = crawl_all_today(db, horizon_days=2)
        n_games = res.get("pulled", 0)
        n_pred = predictor.predict_all_due(db, hours_window=48)
        log.info("[crawl_30d] logs=%s games=%s predictions=%s", n_logs, n_games, n_pred)
    finally:
        db.close()


def predict_3h_job() -> None:
    from ai import predictor

    db = SessionLocal()
    try:
        made = predictor.predict_all_due(db, hours_window=3)
        log.info("[predict_3h] generated=%s", made)
    finally:
        db.close()


def settle_job() -> None:
    """Grade predictions whose games have finished (status=final)."""
    from models import Game, Prediction

    db = SessionLocal()
    try:
        now = datetime.now(config.KST)
        yesterday = now.date() - timedelta(days=1)
        games = (
            db.query(Game)
            .filter(Game.status == "final")
            .filter(Game.game_datetime >= datetime(yesterday.year, yesterday.month, yesterday.day))
            .filter(Game.game_datetime < datetime(now.year, now.month, now.day))
            .all()
        )
        graded = 0
        for g in games:
            pred = db.get(Prediction, g.id)
            if not pred or pred.resolved:
                continue
            h, a = (g.home_score or 0), (g.away_score or 0)
            # moneyline
            pred.ml_correct = (pred.ml_pick == "home" and h > a) or \
                              (pred.ml_pick == "away" and a > h) or \
                              (pred.ml_pick == "draw" and h == a)
            # handicap: home covers if (home - away) > line
            margin = h - a
            pred.hc_correct = (pred.hc_pick == "home" and margin > pred.hc_line) or \
                             (pred.hc_pick == "away" and margin < pred.hc_line)
            # totals
            total = h + a
            pred.tot_correct = (pred.tot_pick == "over" and total > pred.tot_line) or \
                              (pred.tot_pick == "under" and total < pred.tot_line)
            # nrfi: we approximate with final score (1st inning unknown post-hoc
            # without relay data); mark based on whether any run scored overall
            if pred.nrfi_pick:
                scored = h + a > 0
                pred.nrfi_correct = (pred.nrfi_pick == "YRFI" and scored) or \
                                   (pred.nrfi_pick == "NRFI" and not scored)
            pred.resolved = True
            graded += 1
        db.commit()
        log.info("[settle] graded=%s", graded)
    finally:
        db.close()


def start() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = BackgroundScheduler(timezone=config.KST)
    sched.add_job(crawl_30d_job, CronTrigger(hour=3, minute=10, timezone=config.KST), id="crawl_30d", replace_existing=True)
    sched.add_job(predict_3h_job, CronTrigger(minute="*/30", timezone=config.KST), id="predict_3h", replace_existing=True)
    sched.add_job(settle_job, CronTrigger(hour=8, minute=5, timezone=config.KST), id="settle_08", replace_existing=True)
    sched.start()
    _scheduler = sched
    log.info("scheduler started")
    return sched


def shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
