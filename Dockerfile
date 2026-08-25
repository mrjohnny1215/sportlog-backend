# Root-level Dockerfile — Railway fallback build context.
# Builds the FastAPI backend from ./backend regardless of the service's
# Root Directory setting.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["sh", "-c", "python -c 'from database import init_db; init_db()' && uvicorn main:app --host 0.0.0.0 --port 8000"]
