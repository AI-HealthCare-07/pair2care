# Pair2Care LLM 추천 구현

API 명세 11장의 오늘의 한 가지(`DAILY_ACTION`)와 다음 끼니에 바꿀 한 가지(`MEAL_ALTERNATIVE`)를 지원한다. 로그인한 사용자는 생성 요청 후 저장된 결과를 조회할 수 있다. 새 작업은 202, 기존 작업이나 저장본은 200을 반환한다.

## 처리 흐름

- FastAPI는 같은 사용자의 요청을 DB에서 직렬화하고 Redis Stream에 `TaskMessage`를 등록한다. 큐 등록에 실패하면 503을 반환하고 재생성 횟수를 차감하지 않는다.
- 작업 UUID와 DB 행 잠금으로 동시 실행과 이전 작업의 재배달을 구분한다. 워커는 결과와 사용량을 저장한 뒤 Pub/Sub에 알린다. DB에 결과를 남기기 전에 워커가 종료되면 재배달 과정에서 Claude를 다시 호출할 수 있다.
- RAG는 질병관리청 가이드의 행동 후보 4개를 유형과 저장된 입력으로 검색한다. Claude는 후보 ID를 선택하며 API에 표시할 행동과 인용은 서버가 확정한다. 근거가 없으면 Claude 호출 없이 근거 부족 안내를 저장한다.
- 외부 호출에는 허용된 숫자형 식단 값과 고정된 근거 후보만 사용한다. 메뉴 이름과 진단 여부는 서버 내부 검색에만 사용한다. 프롬프트와 응답 원문은 사용량 로그에 저장하지 않는다.

## 로컬 설정과 검증

워커에서 `ANTHROPIC_API_KEY`와 `CLAUDE_MODEL`을 설정한다. 키는 로컬 `.env`나 배포 환경의 시크릿으로 관리한다. Docker 밖에서 워커를 실행할 때는 `uv run --env-file .env --group ai --group app python -m ai_worker.main`을 사용한다. 선택 설정인 `CLAUDE_INPUT_USD_PER_MILLION` 및 `CLAUDE_OUTPUT_USD_PER_MILLION`이 없거나 캐시 토큰이 사용된 경우 추정 비용은 NULL로 저장하고 토큰 수는 별도 필드에 기록한다.

테스트 전용 MySQL과 Redis를 사용한다.

```bash
uv sync --group app --frozen
uv run --group app aerich upgrade
uv run --group app pytest app ai_worker/tests -q
uv run ruff check .
uv run ruff format --check .
```

## 연동 범위

- 최신 `develop`에 `health_profiles`, `meals`, `foods`가 아직 없다. 건강 프로필이 없으면 근거 부족을 반환하고, 식단 테이블을 조회할 수 없으면 식단 API가 503을 반환한다. 테스트는 가상 식단 테이블의 소유권, 음식 선택 여부와 영양 스냅샷을 검증한다. 식단·예측 모델이 들어오면 해당 FK를 연결해야 한다.
- 워커는 `ai:results`를 발행한다. 공통 SSE가 연결되기 전에는 GET으로 상태를 조회할 수 있다.
- 파일 기반 가이드의 범위는 고혈압과 당뇨 식이요법 일부에 한정된다. 라이브 모델의 접근 권한과 프롬프트 캐시 적중 여부는 운영 계정에서 확인해야 한다.
