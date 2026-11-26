# Pair2Care LLM 추천 구현

API 명세 11장의 오늘의 한 가지(`DAILY_ACTION`)와 다음 끼니에 바꿀 한 가지(`MEAL_ALTERNATIVE`)를 지원한다. 로그인한 사용자는 생성 요청 후 저장된 결과를 조회할 수 있다. 새 작업은 202, 기존 작업이나 저장본은 200을 반환한다.

## 처리 흐름

- FastAPI는 같은 사용자의 요청을 DB에서 직렬화하고 Redis Stream에 `TaskMessage`를 등록한다. 큐 등록에 실패하면 503을 반환하고 재생성 횟수를 차감하지 않는다.
- 작업 UUID와 Redis의 만료 가능한 잠금으로 중복 호출을 막는다. Claude 응답을 기다리는 동안 DB 트랜잭션을 열어두지 않으며, 결과 저장 시 현재 작업 UUID와 상태를 행 잠금으로 다시 확인한다. 워커는 결과와 사용량을 저장한 뒤 Pub/Sub에 알린다. DB에 결과를 남기기 전에 워커가 종료되면 재배달 과정에서 Claude를 다시 호출할 수 있다.
- RAG는 질병관리청 등 한국어 공인 자료의 행동 후보 10개를 유형과 저장된 입력으로 규칙 매칭한다(벡터 검색은 아님). Claude는 후보 ID를 선택하며 API에 표시할 행동과 인용은 서버가 확정한다. 근거가 없으면 Claude 호출 없이 근거 부족 안내를 저장한다.
- 외부 호출에는 허용된 숫자형 식단 값과 고정된 근거 후보만 사용한다. 메뉴 이름, 진단 여부, 설문 코드, 생활 기록 원값 및 내부 검색 신호는 서버 내부 검색에만 사용한다. DAILY_ACTION의 meal_facts는 항상 빈 객체다. 전달되는 후보 자체가 건강 관련 맥락을 간접적으로 나타낼 수 있으므로 후보 이외의 개인 건강 데이터는 전달하지 않는다. 프롬프트와 응답 원문은 사용량 로그에 저장하지 않는다.

## DAILY_ACTION 입력 (v4)

- HealthProfileRepository에서 본인의 최신 설문을 읽는다. 기존 진단 여부 및 현재 흡연(BS3_1=1·2)을 유지한다. 음주 경험 BD1=2이고 최근 1년 음주 빈도 BD1_11=2~6이면 음주 상황 대처 계획 후보를 연결한다. 음주량·의존 여부를 추정하지 않으며 일일 음주 기록과는 별개다.
- HealthLogRepository에서 WALK_DAYS, STRENGTH_DAYS, SLEEP 각각 KST 기준 target_on이 속한 주를 우선 조회하고 누락 시 지난주만 조회한다. 날짜 범위는 반개구간으로 제한하고 미래 측정 기록은 제외한다.
- WALK_DAYS=0은 걷기 시작 후보, 1~7일은 기존 습관 유지 후보에 연결한다. 걷기 일수만으로 활동량 부족을 판정하지 않는다.
- STRENGTH_DAYS=0~1은 주 2일 이상 근력 활동을 권고하는 공인 자료에 따라 무리하지 않는 운동 계획 후보로 연결한다. SLEEP은 주중·주말 값이 유효하게 기록된 경우 규칙적인 기상 습관 후보를 연결한다. 수면 시간만으로 장애나 부족 여부를 판정하지 않는다.
- 출처: [질병관리청 운동](https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5293), [금연길라잡이 금연상담전화](https://www.nosmokeguide.go.kr/helpness/counsel), [질병관리청 위험음주](https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5355), [국가정신건강정보포털 수면 습관](https://www.mentalhealth.go.kr/portal/bbs/bbsDetail.do?bbsId=BBSINIT_2&nttId=244). 모든 후보는 원문을 참고한 독자적인 요약·행동 문구다.
- 후보가 없으면 기존 근거 부족 안내와 빈 출처로 COMPLETED 처리하며 Claude 사용량을 기록하지 않는다. 같은 날짜에 이미 COMPLETED 추천이 있으면 재사용한다. 개선 검증 시 새 가상 사용자로 요청한다.
- 일일 운동량·음주 기록, 혈압·혈당 등 나머지 기록의 추천 연결은 적용 근거·조건을 확정한 뒤 추가한다.

## 로컬 설정과 검증

워커에서 `ANTHROPIC_API_KEY`와 `CLAUDE_MODEL`을 설정한다. 키는 로컬 `.env`나 배포 환경의 시크릿으로 관리한다. Docker 밖에서 워커를 실행할 때는 `uv run --env-file .env --group ai --group app python -m ai_worker.main`을 사용한다. 선택 설정인 `CLAUDE_INPUT_USD_PER_MILLION` 및 `CLAUDE_OUTPUT_USD_PER_MILLION`이 없거나 캐시 토큰이 사용된 경우 추정 비용은 NULL로 저장하고 토큰 수는 별도 필드에 기록한다.

테스트 전용 MySQL과 Redis를 사용한다.

```bash
uv sync --group app --frozen
uv run --group app aerich upgrade
uv run --group app python -m pytest app ai_worker/tests -q
uv run ruff check .
uv run ruff format --check .
```

## 연동 범위

- 건강 설문 및 건강 기록 ORM은 연동되었다. 식단 테이블을 조회할 수 없으면 식단 API가 503을 반환한다. 테스트는 가상 식단 테이블의 소유권, 음식 선택 여부와 영양 스냅샷을 검증한다. 식단·예측 모델이 들어오면 해당 FK를 연결해야 한다.
- 워커는 `ai:results`를 발행한다. 공통 SSE가 연결되기 전에는 GET으로 상태를 조회할 수 있다.
- 파일 기반 가이드는 고혈압, 당뇨 식이요법, 걷기, 근력 운동, 수면, 음주 대처 및 금연 상담 일부를 지원한다. 라이브 모델의 접근 권한과 프롬프트 캐시 적중 여부는 운영 계정에서 확인해야 한다.
