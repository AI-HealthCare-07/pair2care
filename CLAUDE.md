# CLAUDE.md

> 에이전트가 작업 전 가장 먼저 읽는 규칙 문서임. 짧게 유지하고, 에이전트가 실수할 때마다 규칙을 한 줄씩 추가함.  
> `TODO` 표시는 주제·스택 확정 후(1~2주차) 채움.

## 1. 프로젝트 개요
- 이름: Pair 2 Care
- 서비스: 만성질환 생활습관 챌린지 웹 서비스 — 필수: 예측 모델, 추적 대시보드, 생활습관 챌린지 / 선택(모두 구현): LLM 예방행동 추천, 식단 이미지 분류·영양 분석, 알림 (원문 `docs/topic_talos.md`)
- 목표: TODO (해결하려는 사용자 문제 한 줄)
- 기간: 2026-11-16 ~ 2026-12-30 데모데이, 12-29 결과 제출 마감
- 팀: OZ 2조 — 역할은 `docs/team.md` 참고

## 2. 기술 스택
- 백엔드: Python 3.13, FastAPI, Tortoise ORM + aerich(마이그레이션), JWT 인증 — 공식 템플릿(`OZ-Coding-School/AI_HealthCare_Final_Project_Template`) 기반
- 패키지: uv (`uv sync --all-groups --frozen`), 의존성 그룹 `app` / `ai` / `dev`로 나눔. 패키지 추가 시 해당 그룹에 넣고 `uv.lock` 같이 커밋
- 프론트엔드: React + Vite (11/17 확정, 바이브 코딩으로 구현)
- DB: MySQL 8.0 (utf8mb4), Redis
- AI: 위험 예측 모델 TODO (XGBoost / LightGBM), Claude API(예방행동 추천), OpenAI `text-embedding-3-small`(RAG 사용 시), TODO (식단 이미지 분류)
- 배포: AWS EC2 + Docker Compose (nginx / fastapi / redis / ai-worker / DB 컨테이너 분리, 멀티스테이지 빌드), 모델·이미지 파일은 S3
- 아키텍처: Client → Nginx(HTTPS·리버스 프록시) → FastAPI(Producer) → Redis Stream(XADD) → AI Worker(Consumer Group, XACK) → Redis Pub/Sub → FastAPI → SSE로 결과 전달
  - 몇 초 이상 걸리는 작업(LLM 추천, 이미지 분류)만 워커로 보냄. 가벼운 예측(트리 모델 추론, ms 단위)은 FastAPI에서 바로 처리
  - 상태 저장은 A안: **워커가 DB의 작업 상태(`meals`·`recommendations`의 PENDING → PROCESSING → COMPLETED / FAILED)를 직접 저장**하고, Pub/Sub은 "끝났다" 알림만 보냄. 기준은 DB
  - 워커 장애 시: 시작할 때 내 Pending 재처리, 5분 넘게 멈춘 작업은 XAUTOCLAIM으로 다른 워커가 가져감, 배달 3번 넘으면 dead-letter(`ai:tasks:dead`)
  - 작업 메시지 형식은 `ai_worker/schemas/task.py`(`TaskMessage`) 한 파일로 고정. Stream에는 `payload` 필드 하나로 넣음

## 3. 디렉토리 구조
```
app/                # FastAPI
├── apis/v1/        # 라우터만. 비즈니스 로직 금지
├── services/       # 비즈니스 로직
├── repositories/   # DB 조회·저장 (서비스는 ORM 직접 호출 대신 여기 사용)
├── models/         # Tortoise 모델
├── dtos/           # 요청·응답 스키마
├── core/           # config, db, jwt, logger
└── tests/
ai_worker/          # Redis Stream 소비자 (tasks/, schemas/)
ml/                 # 예측 모델 학습·검증 (원본 데이터는 레포 밖, ml/README.md)
infra/              # nginx 설정, 배포용 compose
envs/               # example.*.env만 커밋. .local.env / .prod.env 는 커밋 금지
scripts/            # ci(ruff·mypy·테스트), 배포, certbot
frontend/           # React + Vite
docs/               # 기획 문서 4종 + 회의록 (아래 6번)
```
- 폴더마다 규칙이 늘어나면 해당 폴더에 `CLAUDE.md`를 따로 둠.

## 4. 코드 규칙
- 함수·변수: `snake_case` / 클래스: `PascalCase` / 상수: `UPPER_SNAKE`
- 불리언은 `is_`, `has_` 접두사 사용 (예: `is_active`)
- 변수명은 역할이 드러나게 씀 (`user_id` O, `id` X)
- 타입 힌트 필수, 한 함수는 한 가지 일만 함
- 로그는 `print()` 대신 `logger` 사용
- API 응답 형식·엔드포인트·필드명은 `docs/api.md`와 반드시 일치시킴. 명세에 없는 API를 새로 만들 땐 명세부터 수정함
- DB 테이블·컬럼은 `docs/erd.md` 기준. 임의로 컬럼 추가 금지

## 5. AI 기능 규칙
- 개발·테스트는 Claude Haiku, 배포만 Sonnet 사용 (1인 월 $20 크레딧)
- LLM·OCR·임베딩 호출은 `async` + Semaphore로 동시 요청 수 제한, 실패 시 지수 백오프 재시도 최대 3회 (무한 재시도 금지). 테스트는 mock 응답 사용
- 고정 시스템 프롬프트·근거 문서는 Prompt Caching 적용, 같은 질문 결과는 캐싱함
- 모델 학습 실험은 MLflow에 파라미터·데이터 버전·지표 기록. 기록 없는 모델은 배포하지 않음
- 예측 결과는 "위험도 참고값"으로만 표시하고 "진단", "발병 확정" 같은 표현 금지
- LLM 예방행동 추천은 공인 가이드(질병관리청 등) 근거 안에서만 답하게 하고, 근거가 없으면 "모름"으로 답하게 함
- 예측·추천 화면에는 "의료 진단이 아니며 전문가 상담 필요" 안내를 붙임
- 학습 데이터 전처리에서 타깃 누수(예측 대상과 같은 시점·결과에서 나온 컬럼) 금지
- 프롬프트는 코드에 흩어두지 않고 `prompts/` 한 곳에서 관리함

## 6. 문서 (`docs/`)
- `requirements.md` 요구사항 정의서 — 기능 ID `REQ-카테고리-001` 형식 (예: `REQ-USER-001`, 공식 템플릿 기준)
- `wireframe.md` 와이어프레임 링크(Figma)·화면 목록
- `erd.md` ERD·테이블 명세서
- `survey-mapping.md` 설문 ↔ 국건영 코드 대응표 — 예측 입력은 국건영 코드 그대로 저장, 건너뛴 문항 코드 포함
- `api.md` API 명세서 — 각 API에 관련 `REQ-xxx` 표기
- Daily Scrum 기록은 레포가 아니라 노션 팀 페이지에 남김 (평일 10:10)
- 기능 구현 전 해당 `REQ-xxx`와 API 명세를 먼저 읽음

## 7. Git 규칙
- 브랜치: `main`(배포, 보호) ← `develop`(기본) ← `feature/<기능명>`, 긴급 수정은 `hotfix/<내용>`
- 작업은 항상 `develop`에서 새 `feature/` 브랜치를 만들어 시작함
- 커밋: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:` 접두사 + 한국어 요약
- PR은 `develop`으로, 하나의 PR에는 하나의 기능만, 리뷰 1명 승인 후 merge
- 새 기능에는 테스트를 같이 올림. PR 전 `scripts/ci/code_fommatting.sh`(ruff), `scripts/ci/run_test.sh`(mysql 컨테이너 필요) 통과 확인 — CI(`.github/workflows/checks.yml`)도 같은 검사

## 8. 절대 금지
- `main`, `develop`에 직접 push 금지
- API 키·비밀번호·토큰을 코드·문서·커밋·PR에 넣지 않음. 전부 `.env`에 두고 `.env.example`에는 키 이름만 적음 (레포는 6개월간 Public)
- 실제 환자·개인 건강정보를 레포에 커밋하지 않음. 테스트 데이터는 가상 데이터만 사용
- 개인 건강정보(이름, 연락처, 진료 내용)를 로그에 남기지 않음
- 다른 사람 담당 폴더·파일을 상의 없이 크게 고치지 않음
- 대용량 데이터·모델 가중치(`*.csv`, `*.pt`, `*.pkl` 등) 커밋 금지 → `.gitignore` 처리
