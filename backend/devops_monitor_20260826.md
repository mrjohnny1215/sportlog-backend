# SportLog DevOps 모니터링 점검 보고서

> 점검 일시: 2026-08-25 (KST)  
> DB 경로: `/opt/data/sports/backend/sportlog.db`  
> Python venv: `/opt/data/sports/backend/.venv/bin/python`

---

## 1) 컨테이너 / 프로세스 / Health

| 항목 | 상태 |
|------|------|
| 컨테이너 | Docker 미사용 (로컬 실행 환경) |
| uvicorn 프로세스 | 실행 중 (PID `115170`, `0.0.0.0:8000`) |
| API Health | 정상 |

**Health 상세**
```json
{
  "status": "ok",
  "db": "up",
  "games": 32,
  "predictions": 32,
  "tz": "Asia/Seoul"
}
```

---

## 2) 로그

| 항목 | 경로 / 결과 |
|------|------------|
| upcoming_cron.log | `/root/sports/upcoming_cron.log` **없음** |

> 해당 경로에 로그 파일이 존재하지 않습니다.

---

## 3) games 테이블

| 항목 | 값 |
|------|-----|
| scheduled 경기 수 | **32** |
| 최소 100 여부 | ❌ 미달 (100 미만) |

---

## 4) game_logs 테이블

| 항목 | 값 |
|------|-----|
| 총 건수 | **1,761** |
| 날짜 범위 | `2026-02-26` ~ `2026-08-24` |
| 1년치 데이터 충분 여부 | ❌ 부족 (약 6개월치) |

**sport별 분포**

| sport | 건수 |
|-------|------|
| etc | 900 |
| basketball | 286 |
| volleyball | 175 |
| football | 152 |
| baseball | 127 |
| hockey | 121 |

---

## 5) predictions 테이블

| 항목 | 값 |
|------|-----|
| 총 예측 건수 | **32** |
| 커버된 게임 수 | **32** / games 32 |
| 예측 커버리지 | **100.0%** |

> games 테이블의 모든 경기에 예측이 매핑되어 있습니다.

---

## 6) 종합 소견 / 액션 아이템

- [x] API 정상 구동 (`/api/health` 200)
- [ ] **scheduled 경기 수 32 → 목표 100 미달**. 데이터 보강 또는 크롤링/시드 점검이 필요합니다.
- [ ] **game_logs 1년치 부족**. `2026-02-26`부터 데이터가 시작되어 약 6개월만 보유 중입니다.
- [ ] `/root/sports/upcoming_cron.log` 부재 → cron/배치 로그 경로를 확인하고 필요 시 디렉토리/파일을 생성하세요.

---

*자동 생성된 모니터링 보고서*
