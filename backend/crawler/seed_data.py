"""Deterministic seed data generator.

The live Naver parser (see ``naver_sports``) is best-effort. When it cannot
reach the network — or during local/dev runs — this module populates the
database with a *realistic, fully deterministic* dataset so the scoreboard,
AI predictions, hit-rate dashboard and parlay builder all have something to
render. Same DB-less inputs always yield the same numbers.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta

import config
from crawler.weather import VENUES

# ---------------------------------------------------------------------------
# League & team definitions
# ---------------------------------------------------------------------------
LEAGUES: dict[str, dict[str, list[str]]] = {
    "baseball": {
        "KBO": ["두산", "KT", "LG", "NC", "SSG", "롯데", "삼성", "KIA", "한화", "키움"],
        "MLB": ["다저스", "양키스", "레드삭스", "컵스", "브레이브스", "메츠", "필리스", "카디널스",
                "자이언츠", "패드리스", "애스트로스", "메리너스", "오리올스", "가디언스", "트윈스", "레이스"],
        "NPB": ["요미우리", "한신", "요코하마", "히로시마", "야쿠르트", "주니치",
                "소프트뱅크", "오릭스", "세이부", "라쿠텐", "지바롯데", "닛폰햄"],
        "CPBL": ["라이노스", "가디언스", "드래곤즈", "브라더스", "유니라이언스", "몽키스"],
    },
    "football": {
        "KLEAGUE1": ["전북", "서울", "포항", "제주", "광주", "대전", "강원", "수원FC", "울산", "김천", "부산", "인천"],
        "KLEAGUE2": ["성남", "안양", "부천", "춘천", "경남", "김포", "천안", "송도", "수원", "충남"],
        "AMATCH": ["한국", "일본", "이란", "이라크", "호주", "우즈베키스탄", "사우디", "중국", "베트남", "태국"],
        "EPL": ["맨시티", "아스널", "리버풀", "첼시", "토트넘", "맨유", "뉴캐슬", "브라이튼", "애스턴빌라", "웨스트햄"],
        "LALIGA": ["레알마드리드", "바르셀로나", "아틀레티코", "세비야", "비야레알", "레알소시에다드"],
        "BUNDESLIGA": ["바이에른", "도르트문트", "라이프치히", "레버쿠젠", "프라이부르크", "우니온베를린"],
        "SERIEA": ["인터", "유벤투스", "밀란", "나폴리", "로마", "라치오"],
        "LIGUE1": ["파리SG", "모나코", "마르세유", "릴", "렌", "니스"],
        "UCL": ["레알마드리드", "맨시티", "바르셀로나", "아스널", "바이에른", "인터"],
    },
    "basketball": {
        "KBL": ["서울SK", "원주DB", "울산현대모비스", "전주KCC", "고양캐롯", "대구KT", "부산KT", "창원LG", "수원KT", "서울삼성"],
        "WKBL": ["청주KB", "아산우리은행", "용인삼성생명", "부천하나원큐", "인천신한은행"],
        "NBA": ["보스턴", "덴버", "레이커스", "밀워키", "피닉스", "골든스테이트", "뉴욕", "마이애미", "클리블랜드", "오클라호마시티"],
    },
    "volleyball": {
        "VLEAGUE_M": ["천안현대캐피탈", "수원KB손해보험", "인천흥국생명", "대전삼성화재", "의정부KB", "서울우리카드"],
        "VLEAGUE_W": ["화성IBK기업은행", "인천흥국생명", "수원현대건설", "김천KGC", "평택GS칼텍스", "부산경남"],
    },
    "hockey": {
        "NHL": ["보스턴", "콜로라도", "베가스", "탬파베이", "토론토", "에드먼턴", "댈러스", "뉴욕레인저스", "플로리다", "캐롤라이나"],
    },
}

# Which leagues play on a given day. Daily sports (baseball, basketball,
# hockey, volleyball) get a game most days; weekly sports (football) 2-3/week.
DAILY_LEAGUES = ["KBO", "KBL", "WKBL", "NBA", "NHL", "VLEAGUE_M", "VLEAGUE_W"]
WEEKLY_LEAGUES = ["KLEAGUE1", "EPL", "LALIGA", "BUNDESLIGA", "SERIEA", "LIGUE1", "UCL"]


def _rng(seed_str: str) -> random.Random:
    h = hashlib.sha256(seed_str.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _team_rating(team_id: str) -> float:
    """Deterministic hidden strength 0..1 for a team (stable across runs)."""
    h = int(hashlib.sha256(team_id.encode()).hexdigest()[:10], 16)
    return (h % 1000) / 1000.0


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, x))))


def _rating_score(sport: str, rng: random.Random, hr: float, ar: float):
    """Generate a final score using team strength (logistic win prob)."""
    p_home = _logistic((hr - ar) * 6.0)
    home_wins = rng.random() < p_home
    if sport == "baseball":
        base = rng.randint(2, 7)
        if home_wins:
            a = base + rng.randint(0, 4)
            b = rng.randint(0, max(0, a - 1))
        else:
            b = base + rng.randint(0, 4)
            a = rng.randint(0, max(0, b - 1))
        return a, b
    if sport == "football":
        if home_wins:
            a = rng.randint(1, 4)
            b = rng.randint(0, max(0, a - 1))
        else:
            b = rng.randint(1, 4)
            a = rng.randint(0, max(0, b - 1))
        return a, b
    if sport == "basketball":
        a = rng.randint(78, 118) + int(hr * 12)
        b = rng.randint(78, 118) + int(ar * 12)
        if not home_wins:
            a, b = b, a
        if a == b:
            a += 1
        return a, b
    if sport == "volleyball":
        a = rng.randint(70, 115) + int(hr * 15)
        b = rng.randint(70, 115) + int(ar * 15)
        if not home_wins:
            a, b = b, a
        return a, b
    if sport == "hockey":
        if home_wins:
            a = rng.randint(1, 6)
            b = rng.randint(0, max(0, a - 1))
        else:
            b = rng.randint(1, 6)
            a = rng.randint(0, max(0, b - 1))
        return a, b
    a, b = 1, 0
    if not home_wins:
        a, b = b, a
    return a, b


def _venue_for(sport: str, league: str, home: str) -> str:
    if sport == "baseball":
        # map home team to a KBO venue when possible
        mapping = {
            "두산": "KBO:JAMSIL", "LG": "KBO:JAMSIL", "키움": "KBO:GOCHEOK",
            "SSG": "KBO:MUNHAK", "한화": "KBO:DAEJEON", "삼성": "KBO:DAEGU",
            "롯데": "KBO:BUSAN", "KIA": "KBO:GWANGJU", "NC": "KBO:CHANGWON", "KT": "KBO:SUWON",
        }
        return mapping.get(home, "GENERIC:BASEBALL")
    if sport == "football":
        fm = {
            "서울": "KLEAGUE:SEOULWC", "수원FC": "KLEAGUE:SUWONWC", "전북": "KLEAGUE:JEONJU",
            "포항": "KLEAGUE:POHANG", "제주": "KLEAGUE:JEJU", "광주": "KLEAGUE:GWANGJU",
            "대전": "KLEAGUE:DAEGU", "인천": "KLEAGUE:INCHEON",
        }
        return fm.get(home, "GENERIC:FOOTBALL")
    return "INDOOR:GENERIC"


def _score_for(sport: str, rng: random.Random, home_id: str, away_id: str) -> tuple[int, int]:
    return _rating_score(sport, rng, _team_rating(home_id), _team_rating(away_id))


def _team_id(league: str, name: str) -> str:
    return f"{league}:{name}"


def seed_teams(db) -> list:
    """Insert team + venue rows. Idempotent (ignore conflicts)."""
    from models import Team, Venue

    count = 0
    for sport, leagues in LEAGUES.items():
        for league, teams in leagues.items():
            for t in teams:
                tid = _team_id(league, t)
                if db.get(Team, tid) is None:
                    db.add(Team(id=tid, sport=sport, league=league, name=t,
                                short=t[:2], color="#%06x" % _rng(tid).randint(0, 0xFFFFFF)))
                    count += 1
    # venues
    for vid, v in VENUES.items():
        if db.get(Venue, vid) is None:
            db.add(Venue(id=vid, name=v["name"], sport=v["sport"], city=v.get("city"),
                         is_dome=bool(v.get("is_dome")), lat=v.get("lat"), lon=v.get("lon")))
            count += 1
    db.commit()
    return count


def _roll_pair(rng: random.Random, teams: list[str]):
    home = rng.choice(teams)
    away = rng.choice([t for t in teams if t != home])
    return home, away


def _games_count(rng: random.Random, n_teams: int, lo: int, hi: int) -> int:
    """Safe per-league game count: never exceeds available pairings, >= 1."""
    upper = max(1, min(hi, n_teams // 2))
    lower = min(lo, upper)
    return rng.randint(lower, upper)


def generate_game_logs(db, days: int = 30) -> int:
    """Backfill GameLog rows for the past ``days`` (excludes today)."""
    from models import GameLog

    today = datetime.now(config.KST).date()
    n = 0
    for d in range(1, days + 1):
        day = today - timedelta(days=d)
        # daily leagues ~ each league 3-6 games
        for league in DAILY_LEAGUES:
            sport = _sport_of(league)
            teams = LEAGUES[sport][league]
            rng = _rng(f"log|{league}|{day.isoformat()}")
            n_games = _games_count(rng, len(teams), 3, 6)
            for _ in range(n_games):
                home, away = _roll_pair(rng, teams)
                hs, as_ = _score_for(sport, rng, _team_id(league, home), _team_id(league, away))
                vid = _venue_for(sport, league, home)
                db.add(GameLog(
                    sport=sport, league=league, game_date=day,
                    home_team_id=_team_id(league, home), away_team_id=_team_id(league, away),
                    home_team_name=home, away_team_name=away,
                    home_score=hs, away_score=as_, venue_id=vid,
                    details_json={"source": "seed"}, source="seed",
                ))
                n += 1
        # weekly leagues: ~2-3 fixtures 2 days per week
        if day.weekday() in (2, 5):  # Wed, Sat
            for league in WEEKLY_LEAGUES:
                sport = _sport_of(league)
                teams = LEAGUES[sport][league]
                rng = _rng(f"log|{league}|{day.isoformat()}")
                n_games = _games_count(rng, len(teams), 2, 5)
                for _ in range(n_games):
                    home, away = _roll_pair(rng, teams)
                    hs, as_ = _score_for(sport, rng, _team_id(league, home), _team_id(league, away))
                    vid = _venue_for(sport, league, home)
                    db.add(GameLog(
                        sport=sport, league=league, game_date=day,
                        home_team_id=_team_id(league, home), away_team_id=_team_id(league, away),
                        home_team_name=home, away_team_name=away,
                        home_score=hs, away_score=as_, venue_id=vid,
                        details_json={"source": "seed"}, source="seed",
                    ))
                    n += 1
    db.commit()
    return n


def generate_today_games(db, horizon_days: int = 2) -> int:
    """Create scheduled games for today + tomorrow across ALL 5 sports & leagues.

    Every league in :data:`LEAGUES` gets a realistic fixture slate so the
    scoreboard is fully populated even when Naver is unreachable. This replaces
    the old fixed 33-game schedule with full coverage of the product spec.
    """
    from models import Game

    today = datetime.now(config.KST)
    n = 0
    for off in range(horizon_days):
        base_day = today + timedelta(days=off)
        for sport, leagues in LEAGUES.items():
            for league, teams in leagues.items():
                rng = _rng(f"game|{league}|{base_day.date().isoformat()}|{off}")
                # daily sports get more games; weekly fewer
                if league in DAILY_LEAGUES:
                    n_games = _games_count(rng, len(teams), 2, 5)
                else:
                    n_games = _games_count(rng, len(teams), 1, 3)
                for _ in range(n_games):
                    home, away = _roll_pair(rng, teams)
                    hour = 18 if sport in ("baseball", "football") else 19
                    gdt = base_day.replace(hour=hour, minute=30, second=0, microsecond=0)
                    gid = f"{base_day.date().isoformat()}{_team_id(league, away)}{_team_id(league, home)}{off}"
                    vid = _venue_for(sport, league, home)
                    is_dome = bool(VENUES.get(vid, {}).get("is_dome", False))
                    home_sp, away_sp = None, None
                    home_era, away_era = None, None
                    if sport == "baseball":
                        home_sp = f"{home} 선발"
                        away_sp = f"{away} 선발"
                        home_era = round(rng.uniform(2.8, 5.2), 2)
                        away_era = round(rng.uniform(2.8, 5.2), 2)
                    if db.get(Game, gid) is None:
                        db.add(Game(
                            id=gid, sport=sport, league=league, game_datetime=gdt,
                            status="scheduled",
                            home_team_id=_team_id(league, home),
                            away_team_id=_team_id(league, away),
                            home_team_name=home, away_team_name=away, venue_id=vid,
                            home_starter=home_sp, away_starter=away_sp,
                            home_starter_era=home_era, away_starter_era=away_era,
                            is_dome=is_dome,
                        ))
                        n += 1
    db.commit()
    return n


def _sport_of(league: str) -> str:
    for sport, leagues in LEAGUES.items():
        if league in leagues:
            return sport
    return "baseball"
