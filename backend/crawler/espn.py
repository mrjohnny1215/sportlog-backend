"""ESPN public scoreboard crawler — REAL game data, no API key required.

ESPN's ``site.api.espn.com`` scoreboard endpoints are free, CORS-friendly and
return full fixtures (teams, venue, date, scores) for every major league. We
use this as the PRIMARY live source (Naver is geo/header-blocked from the
container), falling back to the deterministic seed generator only when ESPN is
unreachable.

Endpoints
---------
  baseball/mlb        -> MLB
  basketball/nba      -> NBA
  soccer/eng.1        -> EPL
  soccer/esp.1        -> LALIGA
  soccer/ita.1        -> SERIEA
  soccer/ger.1        -> BUNDESLIGA
  soccer/fra.1        -> LIGUE1
  soccer/uefa.champions -> UCL
"""
from __future__ import annotations

import datetime
from typing import Optional

import config
import requests

_ESPN_SPORT = {
    "MLB": "baseball/mlb",
    "NBA": "basketball/nba",
    "EPL": "soccer/eng.1",
    "LALIGA": "soccer/esp.1",
    "SERIEA": "soccer/ita.1",
    "BUNDESLIGA": "soccer/ger.1",
    "LIGUE1": "soccer/fra.1",
    "UCL": "soccer/uefa.champions",
}

# ESPN league -> our sport key
_LEAGUE_SPORT = {
    "MLB": "baseball",
    "NBA": "basketball",
    "EPL": "football",
    "LALIGA": "football",
    "SERIEA": "football",
    "BUNDESLIGA": "football",
    "LIGUE1": "football",
    "UCL": "football",
}

_TIMEOUT = 12


def _espn_url(league: str, date_str: str) -> str:
    sport = _ESPN_SPORT[league]
    return f"https://site.api.espn.com/apis/site/v2/sports/{sport}/scoreboard?dates={date_str}"


def fetch_league_games(league: str, day: datetime.date) -> list[dict]:
    """Return raw game dicts for one league on one day, or [] on failure."""
    date_str = day.strftime("%Y%m%d")
    try:
        r = requests.get(_espn_url(league, date_str), timeout=_TIMEOUT)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []

    sport = _LEAGUE_SPORT[league]
    out = []
    for ev in data.get("events", []):
        comp = ev["competitions"][0]
        competitors = {c["homeAway"]: c for c in comp["competitors"]}
        home = competitors.get("home", {})
        away = competitors.get("away", {})
        home_team = home.get("team", {})
        away_team = away.get("team", {})
        # status: scheduled vs finished
        status_type = ev.get("status", {}).get("type", {})
        state = status_type.get("state", "pre")
        gdt = None
        try:
            gdt = datetime.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            # convert to KST for storage consistency
            gdt = gdt.astimezone(config.KST)
        except Exception:
            gdt = datetime.datetime(day.year, day.month, day.day, 18, 30, tzinfo=config.KST)

        gd = {
            "id": f"espn-{ev['id']}",
            "sport": sport,
            "league": league,
            "game_datetime": gdt,
            "status": "scheduled" if state in ("pre", "in") else "final",
            "home_team_id": f"{league}:{home_team.get('displayName','HOME')}",
            "away_team_id": f"{league}:{away_team.get('displayName','AWAY')}",
            "home_team_name": home_team.get("displayName", "HOME"),
            "away_team_name": away_team.get("displayName", "AWAY"),
            "home_score": int(home["score"]) if home.get("score") and home["score"].isdigit() else None,
            "away_score": int(away["score"]) if away.get("score") and away["score"].isdigit() else None,
            "venue_id": comp.get("venue", {}).get("fullName"),
            "is_dome": bool(comp.get("venue", {}).get("indoor", False)),
        }
        out.append(gd)
    return out


def fetch_all_today(horizon_days: int = 1) -> list[dict]:
    """Collect REAL games for today (and optionally tomorrow) across ESPN leagues."""
    today = datetime.datetime.now(config.KST).date()
    all_games: list[dict] = []
    for off in range(horizon_days):
        day = today + datetime.timedelta(days=off)
        for league in _ESPN_SPORT:
            all_games.extend(fetch_league_games(league, day))
    return all_games
