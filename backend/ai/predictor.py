"""Multi-line AI prediction engine.

For every scheduled game it produces:
  * Moneyline win probabilities (home / draw / away)
  * Handicap (spread) cover pick + probability
  * Totals (Over/Under) pick + probability
  * Baseball 1st-inning NRFI / YRFI pick + probability
  * Value-bet detection (when data favours a side the market under-rates)
  * A 3-line plain-language summary
  * A confidence score (0-100) used by the parlay builder

The engine is a transparent, fully deterministic heuristic model built on the
last-30-day GameLog table plus starter ERA / dome / weather features. No
external model service is required, so predictions are reproducible and the
whole platform runs offline.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

import config
from crawler.weather import get_weather, is_dome_venue

SCORE_CAP = {"baseball": 0.45, "football": 0.55, "basketball": 0.55,
             "volleyball": 0.5, "hockey": 0.55}


def _team_stats(logs: list, team_id: str) -> dict:
    """Aggregate last-30d stats for a team (home & away combined)."""
    wins = draws = losses = 0
    gf = ga = 0
    home_gf = home_ga = away_gf = away_ga = 0
    n = 0
    last10 = []
    for row in logs:
        is_home = row.home_team_id == team_id
        tf = row.home_score if is_home else row.away_score
        ta = row.away_score if is_home else row.home_score
        gf += tf
        ga += ta
        if tf > ta:
            wins += 1
        elif tf == ta:
            draws += 1
        else:
            losses += 1
        if is_home:
            home_gf += tf
            home_ga += ta
        else:
            away_gf += tf
            away_ga += ta
        n += 1
        last10.append((tf, ta))
    last10 = last10[-10:]
    diff = gf - ga
    return {
        "games": n, "wins": wins, "draws": draws, "losses": losses,
        "gf": gf, "ga": ga, "diff": diff,
        "home_gf": home_gf, "home_ga": home_ga,
        "away_gf": away_gf, "away_ga": away_ga,
        "ppg_for": gf / n if n else 0, "ppg_against": ga / n if n else 0,
        "win_pct": wins / n if n else 0.5,
        "last10": last10,
    }


def _h2h(logs: list, home_id: str, away_id: str) -> dict:
    """Head-to-head results from the shared 30d pool (true matchups only)."""
    h_w = a_w = d = 0
    ou_over = 0
    n = 0
    for row in logs:
        if {row.home_team_id, row.away_team_id} == {home_id, away_id}:
            n += 1
            if row.home_team_id == home_id:
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
    return {"games": n, "home_wins": h_w, "away_wins": a_w, "draws": d,
            "home_win_pct": h_w / n if n else 0.5}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, x))))


def _predict_moneyline(home: dict, away: dict, h2h: dict, sport: str) -> dict:
    # Strength = win% blended with differential per game
    h_str = 0.6 * home["win_pct"] + 0.4 * (0.5 + home["diff"] / max(1, home["games"] * 2))
    a_str = 0.6 * away["win_pct"] + 0.4 * (0.5 + away["diff"] / max(1, away["games"] * 2))
    # H2H tilt (only if sample exists)
    if h2h["games"] >= 2:
        h_str = 0.75 * h_str + 0.25 * h2h["home_win_pct"]
    # home edge
    home_edge = 0.03 if sport in ("baseball", "football", "hockey") else 0.02
    h_str += home_edge
    denom = h_str + a_str
    home_p = h_str / denom
    away_p = a_str / denom
    # Calibrate: compress extreme probabilities toward a realistic 50-85% band
    # so the model never reads as 99% certainty (overconfidence guard).
    def _band(p: float) -> float:
        return 50.0 + (p - 0.5) * 0.7 * 100.0

    if sport in ("football", "hockey"):
        draw_p = max(0.0, 0.22 - abs(home_p - away_p) * 0.4)
        home_p = (1 - draw_p) * home_p / (home_p + away_p)
        away_p = (1 - draw_p) * away_p / (home_p + away_p)
        pick = "home" if home_p >= away_p else "away"
        return {"home": round(_band(home_p), 1), "away": round(_band(away_p), 1),
                "draw": round(draw_p * 100, 1), "pick": pick}
    pick = "home" if home_p >= away_p else "away"
    hp = round(_band(home_p), 1)
    ap = round(_band(away_p), 1)
    # Guard: for no-draw sports home+away must sum to 100 (never exceed it).
    if sport not in ("football", "hockey"):
        s = hp + ap
        if s != 100.0 and s > 0:
            hp = round(hp / s * 100.0, 1)
            ap = round(ap / s * 100.0, 1)
    return {"home": hp, "away": ap, "draw": 0.0, "pick": pick}


def _totals_line(sport: str) -> float:
    base = {"baseball": 8.5, "football": 2.5, "basketball": 165.5,
            "volleyball": 180.5, "hockey": 5.5}
    return base.get(sport, 8.5)


def _predict_totals(sport: str, home: dict, away: dict, weather, is_dome: bool) -> dict:
    exp = home["ppg_for"] + away["ppg_for"]  # expected combined scoring pace
    line = _totals_line(sport)
    # weather effects (outdoor only)
    wind = 0.0
    if not is_dome and sport in ("baseball", "football"):
        # stronger wind -> slightly fewer runs/goals in baseball; mild in soccer
        if weather:
            w = weather.wind_speed_ms
            if sport == "baseball":
                wind = -0.04 * (w - 2)  # tails above ~2 m/s
            else:
                wind = -0.02 * (w - 3)
        exp += wind
    # regression toward the league line so we don't overfit extreme runs
    exp_blend = 0.7 * exp + 0.3 * line
    over_p = _logistic((exp_blend - line) * 1.5)
    pick = "over" if over_p >= 0.5 else "under"
    return {"line": line, "pick": pick, "pct": round((over_p if pick == "over" else 1 - over_p) * 100, 1)}


def _predict_handicap(sport: str, home: dict, away: dict, ml: dict) -> dict:
    # expected margin from scoring pace + moneyline edge
    pace = home["ppg_for"] + away["ppg_for"]
    exp_margin = (home["ppg_for"] - away["ppg_for"])
    # convert moneyline prob gap into a line
    gap = (ml["home"] - ml["away"]) / 100.0  # -1..1
    line = round((exp_margin + gap * 1.2), 1)
    # cover probability: home covers if its true edge beats the line
    cover_p = _logistic((exp_margin - line) * 1.2 + gap)
    pick = "home" if cover_p >= 0.5 else "away"
    return {"line": line, "pick": pick, "cover_pct": round((cover_p if pick == "home" else 1 - cover_p) * 100, 1)}


def _predict_nrfi(sport: str, game, weather, is_dome: bool) -> dict | None:
    """Baseball-only 1st-inning NRFI/YRFI."""
    if sport != "baseball":
        return None
    # starter 1st-inning ERA proxy: season ERA scaled (1st inning ~1.15x for many)
    h_era = game.home_starter_era or 4.0
    a_era = game.away_starter_era or 4.0
    # league avg 1st-inning run expectancy ~0.55 runs/game -> NRFI ~55%
    base_nrfi = 0.55
    # better (lower) ERA -> higher NRFI
    era_factor = (9.0 - ((h_era + a_era) / 2)) / 9.0  # 0..1
    nrfi_p = base_nrfi + (era_factor - 0.5) * 0.35
    # wind helps pitchers slightly in baseball
    if weather and not is_dome:
        nrfi_p += -0.01 * (weather.wind_speed_ms - 2)
    nrfi_p = max(0.3, min(0.75, nrfi_p))
    pick = "NRFI" if nrfi_p >= 0.5 else "YRFI"
    return {"nrfi_pct": round(nrfi_p * 100, 1), "yrfi_pct": round((1 - nrfi_p) * 100, 1), "pick": pick}


def _value_bet(ml: dict, sport: str, home: dict, away: dict) -> tuple[bool, str]:
    """Detect when data strongly favours a side but the market line is tight."""
    edge = abs(ml["home"] - ml["away"])
    fav = ml["pick"]
    fav_stats = home if fav == "home" else away
    # strong form (win% > 0.6) yet market near coin-flip -> value
    if fav_stats["win_pct"] >= 0.6 and edge <= 12:
        return True, f"{fav}팀 최근 승률 {fav_stats['win_pct']*100:.0f}%이나 배당 격차는 {edge:.0f}%p에 불과 — [🔥 가치 역배]"
    return False, ""


def _summary(sport: str, ml: dict, tot: dict, hc: dict, nrfi: dict | None, value: tuple) -> str:
    lines = []
    pick = "홈" if ml["pick"] == "home" else ("원정" if ml["pick"] == "away" else "무")
    lines.append(f"승부예측: {pick} 승리({ml[ml['pick']]}%) — 최근 30일 모멘텀 기반.")
    lines.append(f"언더/오버: {tot['line']} 기준 {tot['pick'].upper()} ({tot['pct']}%).")
    if nrfi:
        lines.append(f"1회: {nrfi['pick']} ({nrfi['nrfi_pct'] if nrfi['pick']=='NRFI' else nrfi['yrfi_pct']}%).")
    if value[0]:
        lines.append(value[1])
    return " ".join(lines)


def predict_game(db, game) -> dict:
    """Compute the full prediction dict for one Game row."""
    from models import GameLog

    today = datetime.now(config.KST).date()
    cutoff = today - timedelta(days=30)
    logs = db.query(GameLog).filter(
        GameLog.game_date >= cutoff,
        GameLog.sport == game.sport,
    ).all()

    home = _team_stats(logs, game.home_team_id)
    away = _team_stats(logs, game.away_team_id)
    h2h = _h2h(logs, game.home_team_id, game.away_team_id)

    ml = _predict_moneyline(home, away, h2h, game.sport)
    tot = _predict_totals(game.sport, home, away, None, game.is_dome)
    hc = _predict_handicap(game.sport, home, away, ml)
    nrfi = _predict_nrfi(game.sport, game, None, game.is_dome)
    value = _value_bet(ml, game.sport, home, away)

    conf = round(
        (max(ml["home"], ml["away"], ml.get("draw", 0)))
        + (8 if value[0] else 0)
        + ((nrfi["nrfi_pct"] - 50) / 6 if nrfi else 0)
    )
    conf = max(45.0, min(96.0, conf))

    summary = _summary(game.sport, ml, tot, hc, nrfi, value)

    out = {
        "game_id": game.id,
        "sport": game.sport,
        "league": game.league,
        "ml_home_pct": ml["home"],
        "ml_draw_pct": ml.get("draw", 0.0),
        "ml_away_pct": ml["away"],
        "ml_pick": ml["pick"],
        "hc_line": hc["line"],
        "hc_pick": hc["pick"],
        "hc_cover_pct": hc["cover_pct"],
        "tot_line": tot["line"],
        "tot_pick": tot["pick"],
        "tot_pct": tot["pct"],
        "nrfi_pct": nrfi["nrfi_pct"] if nrfi else None,
        "yrfi_pct": nrfi["yrfi_pct"] if nrfi else None,
        "nrfi_pick": nrfi["pick"] if nrfi else None,
        "value_bet": value[0],
        "value_bet_detail": value[1],
        "confidence": conf,
        "ai_summary": summary,
    }
    return out


def predict_all_due(db, hours_window: int = 48, min_conf: float = 65.0) -> int:
    """Generate predictions for ALL scheduled games due within ``hours_window``.

    Idempotent: skips games that already have a prediction row. Returns the
    number of predictions created. This is the bulk entry point used by the
    server lifespan and the scheduler after a crawl.
    """
    from models import Game, Prediction

    now = datetime.now(config.KST)
    due = (
        db.query(Game)
        .filter(Game.status == "scheduled")
        .filter(Game.game_datetime >= now)
        .filter(Game.game_datetime <= now + timedelta(hours=hours_window))
        .all()
    )
    made = 0
    for g in due:
        if db.query(Prediction).filter(Prediction.game_id == g.id).first():
            continue
        data = predict_game(db, g)
        db.add(Prediction(**data, created_at=now, updated_at=now))
        made += 1
    db.commit()
    return made


def build_parlay(db, min_conf: float = 65.0, max_legs: int = 3) -> dict | None:
    """Pick the best 2-3 leg combo from today's highest-confidence games.

    Returns today's top-``max_legs`` predictions whose confidence clears
    ``min_conf`` (default 65%). When fewer than 2 qualify, returns None so the
    UI can show a calm 'no strong combo today' state.
    """
    from models import Prediction, Game

    today = datetime.now(config.KST).date()
    q = (
        db.query(Prediction, Game)
        .join(Game, Game.id == Prediction.game_id)
        .filter(Prediction.confidence >= min_conf)
        .filter(Game.game_datetime >= datetime(today.year, today.month, today.day))
        .order_by(Prediction.confidence.desc())
        .all()
    )
    if len(q) < 2:
        return None
    legs = q[:max_legs]
    combined = 1.0
    for pred, _ in legs:
        # Normalize any 0..100 percentage into a 0..1 probability before
        # multiplying. Mixing scales produced bogus >100% combined numbers.
        raw = max(pred.ml_home_pct, pred.ml_away_pct, pred.tot_pct, pred.hc_cover_pct)
        p = raw / 100.0 if raw and raw > 1.0 else (raw or 0.0)
        combined *= max(0.0, min(1.0, p))
    combined_pct = round(combined * 100, 1)
    combined_pct = max(0.0, min(100.0, combined_pct))
    return {
        "legs": [
            {
                "game_id": pred.game_id,
                "match": f"{g.away_team_name} @ {g.home_team_name}",
                "pick": pred.ml_pick,
                "confidence": pred.confidence,
            }
            for pred, g in legs
        ],
        "combined_confidence": combined_pct,
    }
