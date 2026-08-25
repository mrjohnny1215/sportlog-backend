# 전광판 AI 5대 스포츠 경기 예측 & 적중률 트래킹 플랫폼

네이버 스포츠 모바일 + 기상 데이터를 기반으로 **야구/축구/농구/배구/하키** 5대 종목의
경기 일정과 최근 30일 전 경기 로그를 수집·분석하여 AI 다각도 예측(승패·핸디캡·언더오버·
야구 1회 NRFI/YRFI·가치역배·2~3폴더 주력)을 자동 생성하고, 전광판 스타일 웹 서비스로
제공하는 풀스택 플랫폼입니다.

## 아키텍처
- **Backend** (`backend/`) — FastAPI + PostgreSQL + APScheduler + 크롤러/AI 엔진 (Docker Compose)
- **Frontend** (`frontend/`) — Next.js(App Router) + Tailwind 전광판 다크 테마 (Vercel 배포)

## 빠른 시작 (Docker)
```bash
cp .env.example .env
docker compose up -d --build
# 백엔드: http://localhost:8000/api/health
# 프론트: Vercel에 frontend/ 디렉토리 연결 (rewrites로 백엔드 프록시)
```

## 오프라인 / 개발 모드
네이버 네트워크 접근이 불가하거나 키가 없으면 `SEED_ENABLED=true` +
`WEATHER_PROVIDER=synthetic` 설정으로 결정론적 시드 데이터가 자동 생성되어
전광판이 비지 않습니다. 동일 입력 → 동일 결과.

## 예측 라이프사이클
- 매일 03:10(KST) 30일 롤링 크롤 + 당일 경기 수집
- 경기 3시간 전(30분 주기 스캔) AI 다각도 예측 생성
- 매일 08:05(KST) 전일 경기 결과로 적중률 자동 정산

## 주요 API
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/games?date=&sport=` | 전광판 매치 카드 |
| GET | `/api/predictions/:id` | 단일 예측 + H2H + 모멘텀 |
| GET | `/api/parlay/today` | 오늘의 2~3폴더 주력 |
| GET | `/api/hitrate?period=30d&sport=` | 라인별 적중률 |
| POST | `/api/vote` | 원클릭 유저 투표(IP 해시) |
| POST | `/api/admin/seed` | 시드 데이터 재생성 |
| POST | `/api/admin/run-predictions` | 예측 강제 생성 |
