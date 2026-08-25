"""Naver Sports crawler (5 sports, all leagues, schedule + 30-day logs).

Strategy
--------
1. ESPN public scoreboard API is tried FIRST as the primary live source — it is
   free, key-less and reachable from most environments (Naver's gateway is often
   geo/header-blocked from servers/containers).
2. Naver's mobile schedule API is then attempted with full browser-masquerade
   headers + exponential-backoff retries. The endpoints used are the JSON
   gateways (NOT HTML scraping):
       https://api-gw.sports.naver.com/schedule/games?fields=basic,superSchedule&date=YYYY-MM-DD
   with per-league category params (kbo/mlb/npb, epl/primera/seriea/bundesliga/
   kleague1, nba/kbl, ...).
3. If *anything* fails (offline, Cloudflare/WAF 403, rate-limit 429, blocked
   region, schema drift) we transparently fall back to the deterministic seed
   generator (``seed_data``) so the platform never shows an empty board.

The parser is intentionally defensive: every external read is wrapped, retries
with backoff, and never raises into the scheduler / lifespan.

Target sports & leagues (full coverage per the product spec):
  * baseball   : KBO, MLB, NPB, CPBL
  * football   : EPL, LALIGA, SERIEA, BUNDESLIGA, LIGUE1, UCL, KLEAGUE1, KLEAGUE2, A-MATCH
  * basketball : NBA, KBL, WKBL
  * volleyball : VLEAGUE_M, VLEAGUE_W
  * hockey     : NHL
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import config
from crawler import seed_data
from crawler.weather import VENUES

# ---------------------------------------------------------------------------
# Browser-perfect masquerade headers (avoids naive-bot WAF / 403 blocks).
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://m.sports.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Naver mobile schedule API gateway.
NAVER_API_GW = "https://api-gw.sports.naver.com"

# Map Naver league category -> our (sport, league) keys.
NAVER_LEAGUES: list[tuple[str, str, str]] = [
    # (naver_category, sport, league)
    ("kbo", "baseball", "KBO"),
    ("mlb", "baseball", "MLB"),
    ("npb", "baseball", "NPB"),
    ("cpbl", "baseball", "CPBL"),
    ("epl", "football", "EPL"),
    ("primera", "football", "LALIGA"),
    ("seriea", "football", "SERIEA"),
    ("bundesliga", "football", "BUNDESLIGA"),
    ("ligue1", "football", "LIGUE1"),
    ("uefaclfinal", "football", "UCL"),
    ("kleague1", "football", "KLEAGUE1"),
    ("kleague2", "football", "KLEAGUE2"),
    # A-MATCH (국가대표) has no stable Naver category id; best-effort only via
    # seed fallback. Kept out of the live call list to avoid non-ascii params.
    ("nba", "basketball", "NBA"),
    ("kbl", "basketball", "KBL"),
    ("wkbl", "basketball", "WKBL"),
    ("vleague_m", "volleyball", "VLEAGUE_M"),
    ("vleague_w", "volleyball", "VLEAGUE_W"),
    ("nhl", "hockey", "NHL"),
]

# Per-attempt retry settings.
MAX_RETRIES = 3
BACKOFF_BASE = 1.5  # seconds; exponential: BASE * 2**attempt
REQUEST_DELAY = (0.8, 1.5)  # polite delay between league calls


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _http_get(url: str, timeout: int = 10) -> bytes | None:
    """GET with browser headers. Returns body bytes or None on any failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def _http_get_with_retry(url: str, timeout: int = 10) -> bytes | None:
    """GET with exponential backoff on 403/429/network errors (max 3 tries)."""
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = e
            # 403 WAF / 429 rate-limit -> back off and retry
            if e.code in (403, 429, 503):
                time.sleep(BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.5))
                continue
            return None  # other HTTP errors are fatal for this URL
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.5))
            continue
    return None


def _parse_dt(raw: str, fallback: datetime) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S",
                "%Y.%m.%d %H:%M", "%Y%m%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=config.KST)
            return dt
        except ValueError:
            continue
    return fallback


def _venue_id_from_name(stadium: str | None) -> tuple[str | None, bool]:
    if not stadium:
        return None, False
    for vid, v in VENUES.items():
        if v["name"] == stadium:
            return vid, bool(v.get("is_dome"))
    return None, False


def _safe_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Naver schedule pull (per-league)
# ---------------------------------------------------------------------------
def _try_naver_league(league_cat: str, date_str: str) -> list[dict] | None:
    """Pull one league's schedule from Naver's mobile API gateway.

    Returns a list of normalized raw game dicts, or None on any failure.
    """
    url = (
        f"{NAVER_API_GW}/schedule/games"
        f"?fields=basic,superSchedule&date={urllib.parse.quote(date_str)}"
        f"&category={urllib.parse.quote(league_cat)}"
    )
    body = _http_get_with_retry(url)
    if not body:
        return None
    try:
        data = json.loads(body.decode("utf-8", "ignore"))
    except (json.JSONDecodeError, AttributeError):
        return None

    # Naver's payload shape is nested; walk the common paths defensively.
    games = (
        data.get("result", {}).get("games")
        or data.get("games")
        or data.get("result", {}).get("schedule", {}).get("games")
        or []
    )
    if not isinstance(games, list):
        return None

    out: list[dict] = []
    for g in games:
        try:
            home = g.get("home", {})
            away = g.get("away", {})
            if not home or not away:
                continue
            raw_dt = (
                g.get("gameDatetime")
                or g.get("startTime")
                or g.get("time")
            )
            fallback = datetime.now(config.KST).replace(hour=18, minute=30)
            gdt = _parse_dt(raw_dt, fallback) if raw_dt else fallback
            stadium = g.get("stadium") or g.get("venue", {}).get("name")
            vid, is_dome = _venue_id_from_name(stadium)
            out.append({
                "naver_id": str(g.get("gameId") or g.get("id") or f"{league_cat}{raw_dt}"),
                "home_name": home.get("name", "홈"),
                "away_name": away.get("name", "원정"),
                "home_code": str(home.get("code", home.get("name"))),
                "away_code": str(away.get("code", away.get("name"))),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
                "game_datetime": gdt,
                "stadium": stadium,
                "venue_id": vid,
                "is_dome": is_dome,
                "home_starter": g.get("homeStarter"),
                "away_starter": g.get("awayStarter"),
                "home_starter_era": _safe_float(g.get("homeStarterEra")),
                "away_starter_era": _safe_float(g.get("awayStarterEra")),
            })
        except Exception:
            continue
    return out if out else None


# ---------------------------------------------------------------------------
# Upcoming games (horizon window)
# ---------------------------------------------------------------------------
def fetch_upcoming_games(db, horizon_days: int = 2) -> int:
    """Populate today/tomorrow games across all sports & leagues.

    Source priority:
      1. ESPN public scoreboard API (real fixtures, no key) — primary live.
      2. Naver mobile schedule API (browser-masqueraded, retried w/ backoff).
      3. Deterministic seed generator so the board is never empty.

    Idempotent across repeated calls (lifespan + scheduler): any previously
    scheduled games inside the horizon window are cleared before re-seeding, so
    re-runs never accumulate duplicate fixtures.
    """
    try:
        from models import Game
        from crawler import espn

        # Clear the horizon window so re-runs don't stack duplicates.
        now = datetime.now(config.KST)
        horizon_end = now + timedelta(days=horizon_days)
        db.query(Game).filter(
            Game.status == "scheduled",
            Game.game_datetime >= now,
            Game.game_datetime <= horizon_end,
        ).delete()
        db.commit()

        raw_games: list[dict] = []

        # (1) ESPN — primary real source.
        try:
            raw_games.extend(espn.fetch_all_today(horizon_days=horizon_days))
        except Exception as e:  # never fatal
            print(f"[crawl] ESPN pass skipped: {e}")

        # (2) Naver — supplement / override where reachable.
        # Skip entirely when NAVER_DISABLED is set (e.g. server/container where
        # Naver is geo/WAF-blocked) to avoid slow retry storms on boot.
        if not config.NAVER_DISABLED:
            today = datetime.now(config.KST)
            for off in range(horizon_days):
                day = today + timedelta(days=off)
                ds = day.strftime("%Y-%m-%d")
                for cat, sport, league in NAVER_LEAGUES:
                    time.sleep(random.uniform(*REQUEST_DELAY))  # rate-limit guard
                    rows = _try_naver_league(cat, ds)
                    if not rows:
                        continue
                    for g in rows:
                        gid = f"naver-{league}-{g['naver_id']}"
                        raw_games.append({
                            "id": gid,
                            "sport": sport,
                            "league": league,
                            "game_datetime": g["game_datetime"],
                            "status": "scheduled",
                            "home_team_id": f"{league}:{g['home_code']}",
                            "away_team_id": f"{league}:{g['away_code']}",
                            "home_team_name": g["home_name"],
                            "away_team_name": g["away_name"],
                            "venue_id": g.get("venue_id"),
                            "is_dome": g.get("is_dome", False),
                            "home_starter": g.get("home_starter"),
                            "away_starter": g.get("away_starter"),
                            "home_starter_era": g.get("home_starter_era"),
                            "away_starter_era": g.get("away_starter_era"),
                        })

        pulled = 0
        for g in raw_games:
            gid = g["id"]
            if db.get(Game, gid):
                continue
            db.add(Game(
                id=gid, sport=g["sport"], league=g["league"],
                game_datetime=g["game_datetime"], status=g["status"],
                home_team_id=g["home_team_id"],
                away_team_id=g["away_team_id"],
                home_team_name=g["home_team_name"],
                away_team_name=g["away_team_name"],
                venue_id=g.get("venue_id"), is_dome=g.get("is_dome", False),
                home_starter=g.get("home_starter"),
                away_starter=g.get("away_starter"),
                home_starter_era=g.get("home_starter_era"),
                away_starter_era=g.get("away_starter_era"),
            ))
            pulled += 1
        db.commit()
        if pulled > 0:
            return pulled
    except Exception as e:
        db.rollback()
        print(f"[crawl] live passes failed: {e}")

    # (3) Fallback: deterministic seed so the board is never empty.
    return seed_data.generate_today_games(db, horizon_days)


# ---------------------------------------------------------------------------
# 30-day historical logs (for momentum / H2H features)
# ---------------------------------------------------------------------------
def fetch_30d_logs(db, days: int = 30) -> int:
    """Backfill the 30-day game-log table. Tries Naver, else seeds deterministically."""
    try:
        from models import GameLog

        today = datetime.now(config.KST).date()
        pulled = 0
        for d in range(1, days + 1):
            day = today - timedelta(days=d)
            ds = day.strftime("%Y-%m-%d")
            for cat, sport, league in NAVER_LEAGUES:
                time.sleep(random.uniform(*REQUEST_DELAY))
                rows = _try_naver_league(cat, ds)
                if not rows:
                    continue
                for g in rows:
                    if not g.get("home_score") or not g.get("away_score"):
                        continue  # only completed fixtures feed logs
                    try:
                        hs = int(g["home_score"])
                        as_ = int(g.get("away_score", 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    db.add(GameLog(
                        sport=sport, league=league, game_date=day,
                        home_team_id=f"{league}:{g['home_code']}",
                        away_team_id=f"{league}:{g['away_code']}",
                        home_team_name=g["home_name"],
                        away_team_name=g["away_name"],
                        home_score=hs, away_score=as_,
                        venue_id=g.get("venue_id"), source="naver",
                    ))
                    pulled += 1
        db.commit()
        if pulled > 0:
            return pulled
    except Exception:
        db.rollback()

    return seed_data.generate_game_logs(db, days)


def crawl_all_today(db, horizon_days: int = 2) -> dict:
    """Collect EVERY real (or seeded) upcoming game across all sports/leagues.

    Returns a summary dict with counts. Designed to be called from the server
    lifespan and the nightly scheduler job.
    """
    n = fetch_upcoming_games(db, horizon_days=horizon_days)
    from models import Game

    breakdown = {}
    total = 0
    for sport in config.SPORTS:
        cnt = db.query(Game).filter(
            Game.sport == sport,
            Game.status == "scheduled",
            Game.game_datetime >= datetime.now(config.KST),
            Game.game_datetime <= datetime.now(config.KST) + timedelta(days=horizon_days),
        ).count()
        breakdown[sport] = cnt
        total += cnt
    return {"pulled": n, "total_scheduled": total, "by_sport": breakdown}
