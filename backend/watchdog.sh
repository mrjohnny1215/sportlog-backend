#!/usr/bin/env bash
# SportLog backend watchdog — keeps uvicorn alive.
# If the server dies (crash/OOM/session cleanup), this loop restarts it
# immediately and logs every (re)start with a timestamp.
set -u

BACKEND_DIR="/opt/data/sports/backend"
VENV="$BACKEND_DIR/.venv/bin/activate"
LOG="$BACKEND_DIR/uvicorn_watchdog.log"
PORT=8000

# Allow disabling the Naver live crawl (geo/WAF-blocked envs) for fast boot.
export DATABASE_URL="${DATABASE_URL:-sqlite:////opt/data/sports/backend/sportlog.db}"
export TZ="${TZ:-Asia/Seoul}"
export SEED_ENABLED="${SEED_ENABLED:-true}"
export WEATHER_PROVIDER="${WEATHER_PROVIDER:-synthetic}"
export NAVER_DISABLED="${NAVER_DISABLED:-true}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(ts)] watchdog started (pid $$)" >> "$LOG"

while true; do
    # Is something already listening on the port? If yes, just wait.
    if curl -s -m 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        sleep 15
        continue
    fi

    echo "[$(ts)] backend NOT responding — starting uvicorn" >> "$LOG"
    # shellcheck disable=SC1091
    source "$VENV"
    cd "$BACKEND_DIR" || exit 1
    uvicorn main:app --host 0.0.0.0 --port "$PORT" >> "$LOG" 2>&1 &
    UVPID=$!
    echo "[$(ts)] uvicorn launched pid=$UVPID" >> "$LOG"

    # Wait for it to either come up or die.
    for i in $(seq 1 40); do
        if curl -s -m 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
            echo "[$(ts)] backend healthy (pid=$UVPID)" >> "$LOG"
            break
        fi
        # If the child died, break inner loop so the outer loop restarts it.
        if ! kill -0 "$UVPID" 2>/dev/null; then
            echo "[$(ts)] uvicorn exited early (pid=$UVPID)" >> "$LOG"
            break
        fi
        sleep 2
    done

    # Block here until the child actually exits, then loop restarts it.
    wait "$UVPID" 2>/dev/null
    echo "[$(ts)] uvicorn stopped — watchdog will restart" >> "$LOG"
    sleep 3
done
