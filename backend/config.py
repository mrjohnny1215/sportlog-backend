"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from datetime import timezone, timedelta

# Korean Standard Time (UTC+09:00)
KST = timezone(timedelta(hours=9))

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sports:sports@postgres:5432/sports"
)

NAVER_BASE = os.getenv("NAVER_BASE", "https://m.sports.naver.com")
NAVER_USER_AGENT = os.getenv(
    "NAVER_USER_AGENT",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
)
# OpenWeatherMap key. When empty the weather module falls back to a synthetic
# but deterministic model so the board works fully offline / in dev.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_PROVIDER = os.getenv("WEATHER_PROVIDER", "synthetic")  # synthetic | openweather

# When no live Naver data is reachable we seed a realistic, deterministic
# dataset so the scoreboard is never empty.
SEED_ENABLED = os.getenv("SEED_ENABLED", "true").lower() in ("1", "true", "yes", "on")

# Set to "1"/"true" to skip the Naver live crawl entirely (e.g. on a server where
# Naver is geo/WAF-blocked) so boot doesn't stall on retry storms. ESPN + seed
# still run.
NAVER_DISABLED = os.getenv("NAVER_DISABLED", "false").lower() in ("1", "true", "yes", "on")

TIMEZONE = os.getenv("TZ", "Asia/Seoul")

# Sports we cover
SPORTS = ["baseball", "football", "basketball", "volleyball", "hockey"]
SPORT_LABELS = {
    "baseball": "야구",
    "football": "축구",
    "basketball": "농구",
    "volleyball": "배구",
    "hockey": "하키",
}
SPORT_EMOJI = {
    "baseball": "⚾",
    "football": "⚽",
    "basketball": "🏀",
    "volleyball": "🏐",
    "hockey": "🏒",
}
