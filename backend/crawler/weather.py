"""Weather & stadium (dome) resolution for the prediction engine.

Naver's mobile scoreboard does not expose structured weather, so this module
works in two modes:

  * ``openweather`` - calls OpenWeatherMap for outdoor venues (needs a key).
  * ``synthetic``   - deterministic pseudo-weather derived from the game date
                      (same input -> same output) so the board is fully
                      reproducible offline and in CI/dev.

Either way the output schema is identical and the predictor only ever sees a
normalised :class:`WeatherSnapshot`.
"""
from __future__ import annotations

import hashlib
import math
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import config

# ---------------------------------------------------------------------------
# Stadium dictionary. ``is_dome`` flags ballparks where weather is irrelevant
# (e.g. Gocheok Sky Dome). Coordinates power the OpenWeather lookups.
# ---------------------------------------------------------------------------
VENUES = {
    # KBO
    "KBO:JAMSIL": dict(name="잠실야구장", sport="baseball", city="서울", is_dome=False, lat=37.5126, lon=127.0717),
    "KBO:GOCHEOK": dict(name="고척스카이돔", sport="baseball", city="서울", is_dome=True, lat=37.4954, lon=126.8667),
    "KBO:MUNHAK": dict(name="인천SSG랜더스필드", sport="baseball", city="인천", is_dome=False, lat=37.4364, lon=126.6893),
    "KBO:DAEJEON": dict(name="한화생명이글스파크", sport="baseball", city="대전", is_dome=False, lat=36.3171, lon=127.4310),
    "KBO:DAEGU": dict(name="대구삼성라이온즈파크", sport="baseball", city="대구", is_dome=False, lat=35.8410, lon=128.6810),
    "KBO:BUSAN": dict(name="사직야구장", sport="baseball", city="부산", is_dome=False, lat=35.1940, lon=129.0640),
    "KBO:GWANGJU": dict(name="기아챔피언스필드", sport="baseball", city="광주", is_dome=False, lat=35.1670, lon=126.8880),
    "KBO:CHANGWON": dict(name="NC파크", sport="baseball", city="창원", is_dome=False, lat=35.2270, lon=128.6810),
    "KBO:SUWON": dict(name="KT위즈파크", sport="baseball", city="수원", is_dome=False, lat=37.2960, lon=127.0130),
    # K League
    "KLEAGUE:SEOULWC": dict(name="서울월드컵경기장", sport="football", city="서울", is_dome=False, lat=37.5680, lon=126.8970),
    "KLEAGUE:SUWONWC": dict(name="수원월드컵경기장", sport="football", city="수원", is_dome=False, lat=37.2950, lon=127.0100),
    "KLEAGUE:JEONJU": dict(name="전주월드컵경기장", sport="football", city="전주", is_dome=False, lat=35.8270, lon=127.1100),
    "KLEAGUE:POHANG": dict(name="포항스틸야드", sport="football", city="포항", is_dome=False, lat=36.0190, lon=129.3430),
    "KLEAGUE:GWANGJU": dict(name="광주축구전용구장", sport="football", city="광주", is_dome=False, lat=35.1610, lon=126.8880),
    "KLEAGUE:DAEGU": dict(name="대구축구전용구장", sport="football", city="대구", is_dome=False, lat=35.8410, lon=128.6810),
    "KLEAGUE:INCHEON": dict(name="인천축구전용구장", sport="football", city="인천", is_dome=False, lat=37.4450, lon=126.6990),
    "KLEAGUE:JEJU": dict(name="제주월드컵경기장", sport="football", city="제주", is_dome=False, lat=33.4770, lon=126.5000),
    "KLEAGUE:GYEONGJU": dict(name="포항인공잔디구장", sport="football", city="경주", is_dome=False, lat=36.0190, lon=129.3430),
    # Basketball / Volleyball / Hockey are played in indoor arenas.
    "INDOOR:GENERIC": dict(name="실내경기장", sport="indoor", city="", is_dome=True, lat=36.5, lon=127.5),
    # Generic fallbacks per sport
    "GENERIC:FOOTBALL": dict(name="종합운동장", sport="football", city="", is_dome=False, lat=37.5, lon=127.0),
    "GENERIC:BASEBALL": dict(name="야구장", sport="baseball", city="", is_dome=False, lat=37.5, lon=127.0),
}

# Outdoor sports where weather matters for totals / NRFI.
OUTDOOR_SPORTS = {"baseball", "football"}


@dataclass
class WeatherSnapshot:
    venue_id: str
    venue_name: str
    is_dome: bool
    temp_c: float
    wind_speed_ms: float
    wind_dir: str
    precip_prob: float  # 0-100
    humidity: float
    source: str  # synthetic | openweather | indoor
    note: str = ""


WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _hash_seed(*parts) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16)


def get_venue(venue_id: str, sport: str = "baseball") -> dict:
    """Return a venue dict, falling back to a generic one for the sport."""
    v = VENUES.get(venue_id)
    if v:
        return v
    if sport == "baseball":
        return VENUES["GENERIC:BASEBALL"]
    if sport == "football":
        return VENUES["GENERIC:FOOTBALL"]
    return VENUES["INDOOR:GENERIC"]


def is_dome_venue(venue_id: str, sport: str = "baseball") -> bool:
    return bool(get_venue(venue_id, sport).get("is_dome"))


def _synthetic_weather(venue: dict, dt: datetime) -> WeatherSnapshot:
    """Deterministic weather from the venue + date. Same args -> same result."""
    seed = _hash_seed(venue.get("lat"), venue.get("lon"), dt.date().isoformat())
    rng = (seed % 1000) / 1000.0  # 0..1
    rng2 = ((seed >> 10) % 1000) / 1000.0
    month = dt.month
    # crude seasonal temp by northern hemisphere month
    base_temp = 22 + 12 * math.sin((month - 4) / 12 * 2 * math.pi)
    temp_c = round(base_temp + (rng - 0.5) * 8, 1)
    wind_speed_ms = round(0.5 + rng2 * 6.5, 1)
    wind_dir = WIND_DIRS[seed % len(WIND_DIRS)]
    precip_prob = round(rng * 35, 0)  # mostly dry in synthetic mode
    humidity = round(45 + rng * 45, 0)
    return WeatherSnapshot(
        venue_id=venue.get("name", ""),
        venue_name=venue.get("name", ""),
        is_dome=bool(venue.get("is_dome")),
        temp_c=temp_c,
        wind_speed_ms=wind_speed_ms,
        wind_dir=wind_dir,
        precip_prob=precip_prob,
        humidity=humidity,
        source="synthetic",
        note="신디케이티드(예측용) 기상 — OpenWeather 키 미설정" if not config.OPENWEATHER_API_KEY else "",
    )


def _openweather_fetch(venue: dict) -> WeatherSnapshot | None:
    key = config.OPENWEATHER_API_KEY
    if not key:
        return None
    lat, lon = venue.get("lat"), venue.get("lon")
    if not lat or not lon:
        return None
    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        + urllib.parse.urlencode({"lat": lat, "lon": lon, "appid": key, "units": "metric", "lang": "kr"})
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sports-ai/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = __import__("json").loads(resp.read().decode())
        wind = data.get("wind", {})
        main = data.get("main", {})
        deg = int(wind.get("deg", 0))
        return WeatherSnapshot(
            venue_id=venue.get("name", ""),
            venue_name=venue.get("name", ""),
            is_dome=bool(venue.get("is_dome")),
            temp_c=round(float(main.get("temp", 20)), 1),
            wind_speed_ms=round(float(wind.get("speed", 0)), 1),
            wind_dir=WIND_DIRS[round(deg / 45) % 8],
            precip_prob=round(float(data.get("clouds", {}).get("all", 0)), 0),
            humidity=round(float(main.get("humidity", 50)), 0),
            source="openweather",
        )
    except Exception as exc:  # network / rate limit -> degrade gracefully
        return None


def get_weather(venue_id: str, sport: str, dt: datetime) -> WeatherSnapshot:
    """Resolve weather for a venue + game time.

    Indoor / dome venues always return a neutral, weather-excluded snapshot.
    """
    venue = get_venue(venue_id, sport)
    if venue.get("is_dome") or sport not in OUTDOOR_SPORTS:
        return WeatherSnapshot(
            venue_id=venue_id,
            venue_name=venue.get("name", ""),
            is_dome=True,
            temp_c=22.0,
            wind_speed_ms=0.0,
            wind_dir="-",
            precip_prob=0.0,
            humidity=50.0,
            source="indoor",
            note="돔/실내 구장 — 기상 영향 제외",
        )

    if config.WEATHER_PROVIDER == "openweather":
        w = _openweather_fetch(venue)
        if w:
            return w
    return _synthetic_weather(venue, dt)
