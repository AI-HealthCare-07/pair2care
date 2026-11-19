# API 명세서 (초안)

> 기준: [erd.dbml](erd.dbml) · [survey-mapping.md](survey-mapping.md) · [requirements.md](requirements.md) · [wireframe.md](wireframe.md) (2026-11-19 develop 기준)
> 담당: 최현영·김민준·장성은. 이 파일은 최현영 담당분(건강 프로필·검진·건강 기록·대시보드) + 공통 규칙 초안. 다른 부분은 담당자가 아래 빈 섹션에 채움
> ⚕️ 표시 응답은 화면에 의료 안내 문구(C-01)를 붙임 (REQ-NFR-001)

## 0. 목차
1. 공통 규칙
2. 인증·회원 — 기존 코드(`/auth`, `/users`) 기준, 담당자 정리 예정
3. **건강 프로필(설문)** — 최현영
4. **검진 수치** — 최현영
5. 예측·습관 시뮬레이션 — 장성은 (작성 중)
6. **건강 기록** — 최현영
7. **대시보드** — 최현영
8. **챌린지·짝꿍** — 최현영 초안 (11/19 PR #30·#31 반영)
10. **식단** — 여현지
11. LLM 추천 / 알림 — 담당 미정
9. 정할 것

---

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 주소 | `/api/v1` (기존 `v1_routers` 그대로) |
| 인증 | `Authorization: Bearer <access_token>`. 이 문서의 API는 모두 로그인 필요 → 없거나 만료되면 401 |
| 내 데이터만 | 경로에 `user_id`를 받지 않음. 토큰의 사용자 기준으로만 읽고 씀. 남의 리소스 id로 접근하면 **404** (존재 여부를 숨김) |
| 필드 이름 | 요청·응답 JSON은 **ERD 컬럼 이름 그대로** snake_case |
| enum | ERD와 같은 대문자 (`ONBOARDING`, `HYPERTENSION`, `BLOOD_PRESSURE` …) |
| 시간 | ISO 8601 + KST 오프셋. datetime `2026-11-19T09:30:00+09:00`, date `2026-11-19` |
| 숫자 | decimal 컬럼(체중·허리둘레·기록 값)은 JSON number로 주고받음 (소수 둘째 자리까지) |
| 목록 | `?limit=20&cursor=<마지막 id>` 커서 방식, 최신순. 응답 `{ "items": [...], "next_cursor": 123 \| null }` |
| 에러 | 기존 코드처럼 FastAPI 기본 형식 `{ "detail": "한국어 메시지" }`. 입력 검사 실패는 FastAPI 기본 422 (`detail`이 배열) |
| 상태 코드 | 200 조회·수정 / 201 생성 / 204 삭제 / 400 규칙 위반 / 401 인증 / 404 없음 / 403 권한 없음(예: 호스트만 가능) / 409 중복·순서 충돌 / 410 만료(예: 초대 링크 7일) / 422 형식 오류 / 429 횟수 제한(예: 응원 하루 1번) |
| 로그 | 요청·응답 본문의 건강 수치는 서버 로그에 남기지 않음 (REQ-NFR-006) |
| 오래 걸리는 작업 | LLM·식단 사진·결과지 OCR은 `202 + task_id` (AI 워커 TaskMessage·SSE와 같은 이름) → Redis Stream 워커 → SSE로 결과 전달 (REQ-NFR-005). 이 문서 담당분은 모두 동기 처리 |

---

## 3. 건강 프로필 (설문) — `health_profiles`

설문 한 번 = 한 행. 가입 설문(`ONBOARDING`)과 주간 재설문(`WEEKLY`)이 같은 API를 씀.

### 3-1. 설문 저장 `POST /api/v1/health-profiles` ⚕️
S-06(가입 설문), S-11(주간 재설문 앞부분) · REQ-PROF-001, PRED-004

**요청**
```json
{
  "kind": "ONBOARDING",
  "survey_version": "2026-11-18",
  "height_cm": 172.5,
  "weight_kg": 78.2,
  "waist_cm": null,
  "father_diabetes_history": 1,
  "mother_diabetes_history": 0,
  "sibling_diabetes_history": 8,
  "father_hypertension_history": 9,
  "mother_hypertension_history": 1,
  "sibling_hypertension_history": 0,
  "alcohol_ever": 2,
  "alcohol_frequency": 5,
  "alcohol_amount": 3,
  "binge_frequency": 2,
  "smoking_lifetime": 3,
  "smoking_current": null,
  "cigarettes_per_day": null,
  "heated_tobacco": 8,
  "liquid_ecig": 8,
  "is_hypertension_diagnosed": false,
  "is_diabetes_diagnosed": false,
  "is_pregnant": null
}
```

**문항별 입력 규칙** (값·코드는 survey-mapping.md 그대로)

| 필드 | 허용 값 | ONBOARDING | WEEKLY |
|---|---|---|---|
| height_cm | 100.0~230.0 | 필수 | 보내지 않음 → 직전 값 복사 |
| weight_kg | 25.0~250.0 | 필수 | 필수 |
| waist_cm | 40.0~200.0 또는 null | 선택 | 선택 (**복사 안 함**, 안 보내면 null) |
| father/mother_*_history | 1 / 0 / 9 | 필수 | 보내지 않음 → 복사 |
| sibling_*_history | 1 / 0 / 9 / 8 | 필수 | 보내지 않음 → 복사 |
| alcohol_ever | 1(없다) / 2(있다) | 필수 | 필수 |
| alcohol_frequency | 1~6 | 해당자 필수 | 해당자 필수 |
| alcohol_amount | 1~5 | 해당자 필수 | 해당자 필수 |
| binge_frequency | 1~5 | 해당자 필수 | 상위 답이 바뀌어 **새로 해당되면 필수**, 계속 해당이면 복사 |
| smoking_lifetime | 3(없음) / 1(5갑 미만) / 2(5갑 이상) | 필수 | 필수 |
| smoking_current | 1 / 2 / 3 | 해당자 필수 | 해당자 필수 |
| cigarettes_per_day | 1~60 | 해당자 필수 | 상위 답이 바뀌어 **새로 해당되면 필수**, 계속 해당이면 복사 |
| heated_tobacco | 8 / 1 / 2 / 3 | 필수 | 보내지 않음 → 복사 |
| liquid_ecig | 8 / 1 / 2 | 필수 | 보내지 않음 → 복사 |
| is_hypertension_diagnosed / is_diabetes_diagnosed | true / false | 필수 | 필수 |
| is_pregnant | 여성: true / false 필수, 남성: null (보내면 400) — **ERD 추가 요청 중** | 필수(여성) | 필수(여성) |

**건너뛰기 처리 (서버가 채움)**
- 화면에서 건너뛴 문항은 클라이언트가 `null`로 보내고, **비해당 코드(8 / 888)는 서버가 채움**. 클라이언트는 8·888을 직접 보내지 않음
  - `alcohol_ever = 1` → alcohol_frequency·alcohol_amount·binge_frequency = 8
  - `alcohol_frequency = 1` → alcohol_amount·binge_frequency = 8
  - `smoking_lifetime = 3` → smoking_current = 8, cigarettes_per_day = 888
  - `smoking_current = 3` → cigarettes_per_day = 888
- 건너뛸 조건인데 값을 보냄(예: `alcohol_ever = 1`인데 `alcohol_frequency = 4`) → **400** `"음주 경험이 없으면 음주 빈도는 보낼 수 없어요."`
- 해당자인데 값이 빠짐(예: `alcohol_frequency = 5`인데 `alcohol_amount = null`) → **400** `"한 번에 마시는 양을 입력해 주세요."`
- WEEKLY의 `binge_frequency`·`cigarettes_per_day` (survey-mapping.md 재설문 규칙): 직전에 비해당(8 / 888)이었는데 이번 답으로 해당되면(예: 비흡연 → 매일 흡연) 다시 받음 → 빠지면 400. 이번 답으로 비해당이 되면 8 / 888 자동 저장. 그 외엔 직전 값 복사
- 나이는 이 행의 `created_at`(KST) 기준 만 나이로 계산 (survey-mapping.md)

**WEEKLY 추가 규칙**
- ONBOARDING 행이 없으면 **409** `"가입 설문을 먼저 해 주세요."`
- ONBOARDING을 두 번 보내면 **409** (수정은 3-4 참고)
- 안 묻는 문항은 클라이언트가 보내도 무시하고 직전 행에서 복사 (위 표)

**처리 순서 (한 트랜잭션)**
1. 검사 → 건너뛰기 코드 채움 → (WEEKLY) 직전 값 복사 → `health_profiles` 저장
2. 예측 서비스 호출 (FastAPI 안에서 바로 추론, REQ-PRED-001) → 질환별 `risk_predictions` 저장. 진단 "예"인 질환은 예측 행을 만들지 않음. **`is_pregnant = true`면 두 질환 모두 예측 안 함** (모델이 임신부를 빼고 학습)
   - 유효한 검진 수치가 있으면 같은 질환에 **모델 점수 행(MODEL) + 기준표 판정 행(CHECKUP_CRITERIA) 둘 다** 저장 (11/19 데이터팀 ERD 요청 ②)
3. 예측 실패 시 설문은 저장하고 응답의 `predictions`를 빈 배열 + `prediction_error: true`로 줌 (설문을 다시 받게 하지 않기 위함)

> 2번 예측 호출의 세부(입력 변환·검진 수치 기준표·응답 상세)는 **5장 예측 API(장성은)** 와 맞춤

**응답 201**
```json
{
  "health_profile": {
    "id": 31,
    "kind": "ONBOARDING",
    "survey_version": "2026-11-18",
    "height_cm": 172.5,
    "weight_kg": 78.2,
    "waist_cm": null,
    "...": "요청 필드 전부 + 서버가 채운 코드",
    "smoking_current": 8,
    "cigarettes_per_day": 888,
    "created_at": "2026-11-19T10:40:00+09:00"
  },
  "predictions": [
    { "id": 51, "disease": "DIABETES", "method": "MODEL", "score": 34, "level": "CAUTION" },
    { "id": 52, "disease": "HYPERTENSION", "method": "MODEL", "score": 21, "level": "LOW" }
  ],
  "managed_diseases": [],
  "skipped_reason": null,
  "prediction_error": false
}
```
- `managed_diseases`: 진단 "예"라서 예측 안 한 질환 → S-09 "관리 중" 카드
- `method`: `MODEL`(설문 모델) / `CHECKUP_CRITERIA`(검진 수치 기준표, 이때 `score`·`model_version`은 null) — 데이터팀 ERD 요청 중. 검진 수치가 있으면 한 질환에 두 행이 같이 옴
- `skipped_reason`: 예측을 아예 안 했을 때 이유 (`PREGNANT` / `AGE_OUT_OF_RANGE`) → S-09에서 일반 안내
- 프론트는 받은 뒤 S-09로 이동해 예측 상세(5장)를 조회

### 3-2. 최근 설문 조회 `GET /api/v1/health-profiles/latest`
S-11 재설문 기본값 채우기, S-27 마이
- 응답 200: 3-1의 `health_profile`과 같은 형태
- 설문이 없으면 **404** `"아직 설문 기록이 없어요."` → 프론트는 S-06으로 보냄

### 3-3. 설문 이력 `GET /api/v1/health-profiles?kind=WEEKLY&limit=20&cursor=`
- `kind` 생략 시 전체. 응답은 공통 목록 형식. 각 항목은 `id, kind, weight_kg, waist_cm, created_at`만(가벼운 목록), 상세는 3-5

### 3-4. 가입 설문 정보 수정 (S-27)
- 행을 고치지 않고 **새 행을 쌓는 게 원칙**(예측 이력의 `health_profile_id`가 가리키는 값이 바뀌면 안 됨)
- 그래서 마이에서 "설문 수정" = `POST /health-profiles` with `kind: "WEEKLY"` + 키·가족력까지 모두 받는 전체 모드 → **정할 것 1번**

### 3-5. 설문 한 건 `GET /api/v1/health-profiles/{id}`
- 응답 200: `health_profile` 형태. 남의 것이면 404

### 3-6. 설문 문항 정의 `GET /api/v1/health-profiles/questions?kind=ONBOARDING`
- 문항 문구·보기·코드·건너뛰기 조건을 서버가 내려줌 → 문구를 바꿔도 프론트 배포 없이 반영, `survey_version`과 같이 관리
- **P2** (처음엔 프론트 상수로 시작해도 됨)
```json
{
  "survey_version": "2026-11-18",
  "questions": [
    { "no": 10, "field": "alcohol_ever", "text": "지금까지 술을 마셔 본 적이 있나요?",
      "type": "SINGLE", "options": [{"label": "없다", "value": 1}, {"label": "있다", "value": 2}],
      "skip": [{"when": 1, "fields": ["alcohol_frequency", "alcohol_amount", "binge_frequency"]}] }
  ]
}
```

---

## 4. 검진 수치 — `checkup_records`
S-07(직접 입력), S-08(결과지 인식, P2) · REQ-PROF-002·003

### 4-1. 저장 `POST /api/v1/checkup-records` ⚕️
```json
{
  "checked_on": "2026-05-10",
  "systolic_bp": 134,
  "diastolic_bp": 86,
  "fasting_glucose": 108,
  "waist_cm": 91.0,
  "triglyceride": 162,
  "hdl_cholesterol": 44,
  "hba1c": 5.8,
  "source": "MANUAL"
}
```
| 필드 | 규칙 |
|---|---|
| checked_on | 필수. 오늘(KST) 이후 날짜 불가 → 400 |
| systolic_bp | 60~260 또는 null |
| diastolic_bp | 30~160 또는 null. 둘 다 있으면 수축기 > 이완기 아니면 400 |
| fasting_glucose | 40~600 또는 null |
| waist_cm | 40.0~200.0 또는 null |
| triglyceride | 20~2000 또는 null (mg/dL) — **ERD 추가 요청 중** |
| hdl_cholesterol | 10~150 또는 null (mg/dL) — **ERD 추가 요청 중** |
| hba1c | 3.0~15.0 또는 null (%) — **ERD 추가 요청 중** |
| source | `MANUAL`(기본) / `OCR` |
| 공통 | 수치 중 **최소 1개** 필요 → 없으면 400 `"검진 수치를 하나 이상 입력해 주세요."` |

- 저장 후 최근 설문 + 이 검진 기록으로 **예측을 다시 계산**(5장, `checkup_record_id` 채움)
  - 모델 점수 행(`MODEL`)은 항상 저장하고, 검진 수치가 있는 질환은 **기준표 판정 행(`CHECKUP_CRITERIA`)을 하나 더 저장** (정할 것 9번)
  - "관리 중"은 설문에서 진단 "예"일 때만 씀. 검진 수치가 기준 범위여도 "관리 중"으로 바꾸지 않음
- 응답 201: 저장된 행 + 3-1과 같은 `predictions` / `managed_diseases` / `prediction_error`
- 화면 표현은 "진단"이 아니라 "수치가 고혈압 범위예요, 병원 확인을 권해요" (S-09)

### 4-2. 목록 `GET /api/v1/checkup-records?limit=20&cursor=`
- `checked_on` 최신순

### 4-3. 한 건 `GET /api/v1/checkup-records/{id}`

### 4-4. 수정 `PATCH /api/v1/checkup-records/{id}`
- 보낸 필드만 바꿈, 규칙은 4-1과 같음(수정 후에도 최소 1개). `updated_at` 갱신
- 수정해도 **지난 예측 행은 그대로** 두고(`input_snapshot`에 당시 값이 있음), 이 기록이 가장 최근 검진이면 예측을 새로 한 번 계산

### 4-5. 삭제 `DELETE /api/v1/checkup-records/{id}` → 204
- 이 기록을 참조한 `risk_predictions.checkup_record_id`는 null로 (FK `ON DELETE SET NULL` 필요 → **정할 것 2번**)

### 4-6. 결과지 인식 (P2, 12/4 이후, 김지연)
- `POST /api/v1/checkup-records/ocr` (multipart 사진) → 202 `{ "task_id": "..." }` → SSE로 읽은 수치 → 사용자가 확인 후 4-1에 `source: "OCR"`로 저장
- 결과지에 없는 항목은 null 그대로(추정해서 채우지 않음), 이름·주민번호는 LLM 전에 지움 (REQ-NFR-010)

---

## 6. 건강 기록 — `health_logs`
S-19(일일 기록), S-11 뒷부분(주간 기록 6종), S-12 컨디션 · REQ-DASH-001·005

### 6-0. 종류별 값 규칙
일일 기록은 ERD에 값 규칙이 없어서 아래처럼 제안 (**정할 것 3번**). 주간 기록은 ERD 그대로.

| log_type | value | value2 | unit | 범위 | 주기 |
|---|---|---|---|---|---|
| BLOOD_PRESSURE | 수축기 | 이완기 (필수) | `mmHg` | 60~260 / 30~160 | 수시 (하루 여러 번 가능) |
| BLOOD_GLUCOSE | 혈당 | — | `mg/dL` | 40~600 | 수시 |
| ALCOHOL | 마신 잔 수 (소주잔 기준) | — | `drinks` | 0~50 | 하루 1행 권장 |
| EXERCISE | 운동 시간 | — | `minutes` | 1~600 | 수시 |
| STEPS | 걸음 수 (직접 입력) | — | `steps` | 0~100000 | 하루 1행, 다시 입력하면 덮어씀 |
| CONDITION | 좋음 2 · 보통 1 · 나쁨 0 | — | null | 0~2 | 하루 1행, 덮어씀 |
| WEIGHT | 체중 | — | `kg` | 25~250 | 수시 |
| WALK_DAYS | 0~7 | — | `days_per_week` | | 주 1행 |
| STRENGTH_DAYS | 0~5 (5 = 5일 이상) | — | `days_per_week` | | 주 1행 |
| SITTING_HOURS | 0~24 | — | `hours_per_day` | | 주 1행 |
| SLEEP | 주중 시간 | 주말 시간 (필수) | `hours_per_day` | 0~24 | 주 1행 |
| BREAKFAST | 0~3 | — | null | | 주 1행 |
| STRESS | 0~3 | — | null | | 주 1행 |

- `unit`은 **서버가 종류에 맞게 채움** (클라이언트가 보내도 무시)
- 실천 기록만으로 "위험이 줄었다"는 문구를 만들지 않음 (REQ-NFR-003). 이 API는 값만 저장

### 6-1. 일일 기록 저장 `POST /api/v1/health-logs`
```json
{ "log_type": "BLOOD_PRESSURE", "value": 132, "value2": 84, "measured_at": "2026-11-19T07:40:00+09:00", "memo": "아침 약 먹기 전" }
```
- 주간 6종(`WALK_DAYS` 등)을 여기로 보내면 400 `"주간 기록은 주간 기록 API로 저장해 주세요."`
- `measured_at` 미래 불가(5분 여유), 생략하면 지금
- STEPS·CONDITION은 같은 날(KST)에 이미 있으면 **덮어쓰고 200**, 없으면 201
- 응답: 저장된 행 `{ id, log_type, value, value2, unit, measured_at, memo, created_at }`

### 6-2. 기록 조회 `GET /api/v1/health-logs?log_type=BLOOD_PRESSURE&from=2026-11-01&to=2026-11-19`
- `log_type` 필수(여러 개는 쉼표), `from`·`to`는 KST 날짜(양끝 포함), 최대 366일
- `measured_at` 오름차순(그래프용), 최대 1000건 → 넘으면 400으로 기간 줄이기 안내
```json
{ "items": [ { "id": 901, "log_type": "BLOOD_PRESSURE", "value": 132, "value2": 84, "unit": "mmHg", "measured_at": "2026-11-19T07:40:00+09:00", "memo": "아침 약 먹기 전" } ] }
```

### 6-3. 수정 `PATCH /api/v1/health-logs/{id}` / 삭제 `DELETE /api/v1/health-logs/{id}` → 204
- 수정 가능: `value`, `value2`, `measured_at`, `memo` (`log_type`은 못 바꿈 → 지우고 새로)
- ERD에 `updated_at`이 없음 → 수정 허용할지 **정할 것 4번** (안 하면 삭제 후 재입력만)

### 6-4. 주간 기록 저장 `PUT /api/v1/health-logs/weekly/{week_start}`
S-11 뒷부분. `week_start` = 그 주 **월요일** 날짜 (`2026-11-16`). 월요일이 아니면 400
```json
{
  "walk_days": 3,
  "strength_days": 1,
  "sitting_hours": 9,
  "sleep_weekday_hours": 6.5,
  "sleep_weekend_hours": 8,
  "breakfast": 2,
  "stress": 1
}
```
- 모두 선택. **보낸 항목만** 그 주 1행으로 저장·덮어씀(`measured_at` = 월요일 00:00 KST), `null`을 보내면 그 항목 삭제, 안 보낸 항목은 그대로
- 수면은 주중·주말 둘 다 있어야 저장 (한쪽만 오면 400)
- 이번 주·지난주만 저장 가능 (더 과거·미래는 400) → 늦게 하는 사람 배려
- 응답 200: 아래 6-5와 같은 형태

### 6-5. 주간 기록 조회 `GET /api/v1/health-logs/weekly/{week_start}`
```json
{ "week_start": "2026-11-16", "walk_days": 3, "strength_days": 1, "sitting_hours": 9,
  "sleep_weekday_hours": 6.5, "sleep_weekend_hours": 8, "breakfast": 2, "stress": 1 }
```
- 없는 항목은 null (404 아님)

---

## 7. 대시보드
S-18, S-12 일부 · REQ-DASH-002·003·004

### 7-1. 위험도 추이 `GET /api/v1/dashboard/risk-trend?weeks=12` ⚕️
- 질환별로 **주(월~일)마다 마지막 예측 1개**, 최근 N주(기본 12, 최대 52)
```json
{
  "series": [
    { "disease": "DIABETES", "managed": false,
      "points": [ { "week_start": "2026-11-16", "score": 34, "level": "CAUTION", "prediction_id": 51 } ] },
    { "disease": "HYPERTENSION", "managed": true, "points": [] }
  ]
}
```
- `managed: true` = 최근 설문에서 진단 "예" → 추이 대신 "관리 중" 카드
- 예측이 없는 주는 점을 빼고 보냄(0으로 채우지 않음)
- 추이는 `method = MODEL`인 점만 이어 그림. 기준표 판정(`CHECKUP_CRITERIA`, score 없음)은 그 주에 표시만 따로 (`criteria_level`) → 정할 것 9번
- "위험도가 낮아졌어요"는 **직전 점보다 실제로 내려갔을 때만**, 바뀐 입력값과 같이 보여줌 (REQ-NFR-003) → 바뀐 입력값은 예측 상세(5장)의 `input_snapshot` 비교로

### 7-2. 항목별 그래프 `GET /api/v1/dashboard/logs?log_type=BLOOD_PRESSURE&from=&to=&bucket=day`
- `bucket`: `raw`(그대로, 기본) / `day` / `week`. 묶을 때는 평균, 혈압은 수축기·이완기 각각 평균
- 혈압 그래프는 **집에서 잰 값(health_logs)만**, 검진 수치는 섞지 않음 (REQ-DASH-002)
```json
{ "log_type": "BLOOD_PRESSURE", "unit": "mmHg", "bucket": "day",
  "points": [ { "date": "2026-11-18", "value": 131.5, "value2": 83.0, "count": 2 } ] }
```

### 7-3. 요약 카드 `GET /api/v1/dashboard/summary?week_start=2026-11-16`
대시보드 첫 화면 한 번에. `week_start` 생략 시 이번 주
```json
{
  "week_start": "2026-11-16",
  "priority_disease": "DIABETES",
  "latest_risk": [ { "disease": "DIABETES", "score": 34, "level": "CAUTION", "created_at": "2026-11-19T10:40:00+09:00" } ],
  "logs": {
    "BLOOD_PRESSURE": { "count": 4, "avg_value": 131.2, "avg_value2": 83.5, "last_measured_at": "2026-11-19T07:40:00+09:00" },
    "STEPS": { "days_logged": 3, "avg_value": 6120 }
  },
  "weekly_record_done": true,
  "challenge": { "achieved_checks": 4, "target_checks": 6, "achievement_rate": 0.67 },
  "meal": null
}
```
- `priority_disease`: 먼저 보여줄 카드(S-18 "고혈압·당뇨에 따라 먼저 보여줄 카드가 다름"). 최근 예측 level이 더 높은 질환, 같으면 score가 높은 쪽, "관리 중"이면 그 질환 우선
- `challenge`: 이번 주 체크 수 ÷ 목표 횟수 → 챌린지 API 담당과 계산식 맞춤
- `meal`: 식단은 P2라 처음엔 null, 붙으면 `{ "kcal_avg": ..., "sodium_avg_mg": ... }`
- 문구는 "~를 달성했어요!" 같은 달성률로만 (REQ-NFR-003)

---

## 8. 챌린지·짝꿍
S-13~S-17 · REQ-CHAL-001~004, PAIR-001~004 · 근거: erd.dbml, erd.md "짝꿍 챌린지 결정(11/19)", [짝꿍챌린지_구체화_제안.md](짝꿍챌린지_구체화_제안.md)

**공통 원칙**
- 짝꿍에게 보이는 건 **닉네임 + 날짜별 완료 여부(`checked_on`)뿐**. 건강 수치·검진·위험도·기록은 어떤 응답에도 넣지 않음 (REQ-PAIR-003). 체중 챌린지도 "쟀다/안 쟀다"만
- 참여자가 아닌 챌린지·남의 짝꿍 관계는 404
- 범위: 12/4까지 **혼자(SOLO)·1:1(PAIR)**, 1:N(GROUP)은 그 다음. 같은 API에 `mode`만 추가하는 구조라 12/4 이후 엔드포인트가 늘지 않음
- **`mode`는 DB에 저장하지 않고 응답에서 계산** (ERD 컬럼 추가 없음): `pair_id`가 있으면 `PAIR` / 아니고 남은 참여자(INVITED·JOINED)가 2명 이상이면 `GROUP` / 그 외 `SOLO` → `continue-solo` 뒤엔 `pair_id`가 비어 `SOLO`로 보임. 8-7 요청의 `mode`는 초대 인원 검사에만 씀
- **호스트(owner)** = `challenges.created_by` ("현재 호스트" 뜻, ERD Note에 표기 예정). 방장·리더 대신 이 용어로 통일 (짝꿍 사이에 위아래가 생기지 않게)

### 8-1. 기본 목록 `GET /api/v1/challenge-templates`
```json
{ "items": [ { "id": 1, "title": "10분 걷기", "category": "WALK", "default_times_per_week": 3 },
             { "id": 6, "title": "주 N회 체중 재기", "category": "WEIGHT", "default_times_per_week": 2 },
             { "id": 7, "title": "금연", "category": "NO_SMOKING", "default_times_per_week": 7 } ] }
```
- 걷기·물·운동·스트레칭·절주·체중·금연 (PR #31)
- `category`: 대문자 7종 `WALK`·`WATER`·`EXERCISE`·`STRETCH`·`LESS_ALCOHOL`·`WEIGHT`·`NO_SMOKING` (11/19 확정)

### 8-2. 짝꿍 초대 만들기 `POST /api/v1/pairs/invites` → 201
요청 본문 없음. `pairs` 1행 생성: `requester_id = 나`, `partner_id = null`, `status = PENDING`, `invite_code` = 추측 불가능한 랜덤 문자열(`secrets.token_urlsafe(32)`)
```json
{ "pair_id": 12, "invite_code": "Xk3...", "invite_url": "https://<도메인>/invite/Xk3...", "status": "PENDING", "created_at": "2026-11-19T11:50:00+09:00" }
```
- 초대 링크는 `created_at` 기준 **7일 지나면 만료** (11/19 확정, 컬럼 추가 없음) → 8-3·8-4에서 만료로 응답
- 보내 놓고 아무도 안 받은 초대(PENDING, 만료 전)는 1인당 최대 5개 → 넘으면 409 `"보낸 초대가 많아요. 안 쓰는 초대를 먼저 취소해 주세요."`

### 8-3. 초대 미리보기 `GET /api/v1/pairs/invites/{invite_code}`
초대 링크를 연 사람에게 "○○님이 짝꿍 초대를 보냈어요" 화면용
```json
{ "requester_nickname": "현영", "status": "PENDING", "expires_at": "2026-11-26T11:50:00+09:00" }
```
- 로그인 필요 (닉네임 외 정보 없음). 없는 코드 404, PENDING이 아니면 `status`로 알려 줌 → 프론트가 "이미 사용된 초대예요" 표시
- 7일이 지난 PENDING은 `status: "EXPIRED"`로 내려줌 (DB 값은 PENDING 그대로, 응답에서만 계산)

### 8-4. 초대 수락 `POST /api/v1/pairs/invites/{invite_code}/accept` → 200
처리 (한 트랜잭션)
1. 행 잠금(`select_for_update`) 후 `status = PENDING` 확인. 아니면 409 `"이미 사용된 초대예요."` / 7일 지났으면 410 `"초대 링크가 만료됐어요. 새 링크를 받아 주세요."`
2. `requester_id = 나`면 400 `"내가 보낸 초대는 수락할 수 없어요."`
3. `partner_id = 나`, `status = ACCEPTED`, `accepted_at = 지금`, **`pair_key = "작은 id:큰 id"`** 채움
4. 이미 같은 두 사람이 ACCEPTED면 `pair_key` 유니크 위반 → 409 `"이미 짝꿍이에요."` (A→B·B→A 동시 수락도 DB가 막음)
```json
{ "pair_id": 12, "partner": { "user_id": 7, "nickname": "현영" }, "status": "ACCEPTED", "accepted_at": "2026-11-19T12:00:00+09:00" }
```
- 거절 API는 따로 두지 않음 (링크를 무시하면 됨). 보낸 사람은 8-6으로 취소

### 8-5. 내 짝꿍 목록 `GET /api/v1/pairs?status=ACCEPTED`
```json
{ "items": [ { "pair_id": 12, "partner": { "user_id": 7, "nickname": "현영" }, "status": "ACCEPTED", "accepted_at": "..." } ] }
```
- `status=PENDING`: 내가 보낸 미수락 초대 (`invite_url` 포함)
- `partner`는 내가 requester든 partner든 "상대방"으로 내려줌

### 8-6. 초대 취소·짝꿍 끊기 `POST /api/v1/pairs/{pair_id}/end` → 200
- PENDING(내가 보낸 것) → ENDED: 초대 취소
- ACCEPTED(둘 중 누구나) → ENDED, **`pair_key = null`로 비움** → 나중에 다시 짝꿍 맺기 가능
- 진행 중인 1:1 챌린지: 끊은 사람은 LEFT, 남은 사람은 **"종료 / 혼자 계속"을 직접 고름** (자동으로 계속하지 않음) → 8-8
- 1:N 챌린지: 끊은 사람만 LEFT, 나머지는 계속 (11/19 확정)

### 8-7. 챌린지 만들기 `POST /api/v1/challenges` → 201
S-14, S-10 "이걸로 챌린지 만들기"
```json
{
  "challenge_template_id": 1,
  "title": "점심 먹고 10분 걷기",
  "times_per_week": 3,
  "starts_on": "2026-11-23",
  "ends_on": "2026-12-20",
  "mode": "PAIR",
  "invite_user_ids": [7]
}
```
| 필드 | 규칙 |
|---|---|
| challenge_template_id | 기본 목록 id 또는 null(직접 만들기) |
| title | 1~100자. 생략하면 템플릿 제목 |
| times_per_week | 1~7 |
| starts_on | 오늘(KST) 이후. 생략하면 오늘 |
| ends_on | null(기한 없음) 또는 starts_on 이후 |
| mode | `SOLO` / `PAIR`(1:1) / `GROUP`(1:N, 12/4 이후) |
| invite_user_ids | SOLO: 빈 배열 / PAIR: 정확히 1명 / GROUP: 1~3명 (나 포함 2~4명) |

**검사**
- 초대 대상은 모두 **나와 ACCEPTED인 짝꿍**이어야 함 → 아니면 400 `"짝꿍으로 맺은 사람만 초대할 수 있어요."`
- PAIR: 그 짝꿍의 `pairs.id`를 `challenges.pair_id`에 넣음 / GROUP·SOLO: `pair_id = null`

**저장 (한 트랜잭션)**
1. `challenges` 1행, `status = ACTIVE`, `created_by = 나`
2. `challenge_participants`: **만든 사람(= 호스트)은 `JOINED` + `joined_at = 지금`**, 초대한 사람은 `INVITED`
3. 초대 알림 생성 (알림 담당과 맞춤)

응답: 8-9 상세와 같은 형태

### 8-8. 챌린지 초대 수락·거절·나가기·종료 (11/19 확정)
| API | 누가 | 바뀌는 상태 | 규칙 |
|---|---|---|---|
| `POST /api/v1/challenges/{id}/join` | 초대받은 사람 | INVITED → JOINED, `joined_at = 지금` | `times_per_week`(개인 목표)를 같이 보낼 수 있음, 안 보내면 챌린지 기본값 |
| `POST /api/v1/challenges/{id}/decline` | 초대받은 사람 | INVITED → LEFT | |
| `POST /api/v1/challenges/{id}/leave` | 참여자 | JOINED → LEFT | 체크 기록은 남김. 1:N 호스트면 아래 "호스트 넘기기", 1:1이면 남은 사람이 고르기 |
| `PATCH /api/v1/challenges/{id}/me` | 참여자 | 개인 목표 변경 | 1~7, 다음 주 월요일부터 적용 (이번 주 칸 수가 바뀌지 않게) |
| `PATCH /api/v1/challenges/{id}` | **호스트만** | 제목·기간·기본 횟수 수정 | 그 외 403 `"호스트만 바꿀 수 있어요."` |
| `POST /api/v1/challenges/{id}/invites` | **호스트만** | 짝꿍 추가 초대 (INVITED) | 1:N만, 8-7과 같은 검사 (짝꿍만, 총 4명까지) |
| `POST /api/v1/challenges/{id}/end` | **호스트만** | ACTIVE → ENDED | **JOINED가 나 혼자일 때만**. 같이 하는 사람이 있으면 409 `"함께하는 분이 있어서 끝낼 수 없어요."` 삭제가 아니라 ENDED (기록 보존) |

**호스트가 나갈 때 — 1:N만 (호스트 넘기기)**
```json
POST /api/v1/challenges/{id}/leave
{ "new_owner_user_id": 7 }
```
- `new_owner_user_id`: 남은 JOINED 중 한 명. 안 보내면 **먼저 들어온 사람**(`joined_at`이 가장 빠른 JOINED)
- 넘긴 뒤 나는 LEFT, `challenges.created_by`를 새 사람으로 바꿈 (`created_by` = 현재 호스트, 11/19 ERD 확정)
- 화면: 1:N은 "이제 ○○님이 호스트예요" 안내 / **1:1은 호스트를 화면에 표시하지 않음**
- 1:1에서 호스트가 나가면 넘기기 없이 아래 "남은 사람이 고르기"로 감 (`new_owner_user_id`를 보내도 무시)
- 남은 JOINED가 없으면 나가기 대신 `end`로 안내 (400)

**1:1에서 짝꿍이 끊거나 나갔을 때 — 남은 사람이 고르기**
- 조건: `pair_id`가 있는 챌린지에서 상대가 LEFT이거나 짝꿍이 ENDED → 목록·상세 응답에 `"decision_required": true`
- 고르기 전엔 체크 불가 (400 `"계속할지 먼저 골라 주세요."`) → 자동으로 계속되지 않게

| 선택 | API | 처리 |
|---|---|---|
| 혼자 계속 | `POST /api/v1/challenges/{id}/continue-solo` | `pair_id = null` → 혼자 챌린지로 (참여 기록은 `challenge_participants`에 남음) |
| 종료 | `POST /api/v1/challenges/{id}/end` | ACTIVE → ENDED (이 경우는 남은 사람이 호스트가 아니어도 허용) |

- 컬럼 추가 없이 "`pair_id`가 남아 있고 상대가 빠졌는지"로 판단

### 8-9. 챌린지 목록·상세
`GET /api/v1/challenges?status=ACTIVE` (S-13, 홈 S-12) — 내가 INVITED·JOINED인 것
```json
{ "items": [ {
  "id": 30, "title": "점심 먹고 10분 걷기", "mode": "PAIR", "status": "ACTIVE",
  "my_status": "JOINED", "my_times_per_week": 3,
  "this_week": { "checked": 2, "target": 3 }, "total_checked": 9,
  "streak_weeks": 2, "checked_today": false,
  "is_owner": true, "decision_required": false
} ] }
```
`GET /api/v1/challenges/{id}` (S-15, S-17)
```json
{
  "id": 30, "title": "점심 먹고 10분 걷기", "mode": "PAIR", "times_per_week": 3,
  "starts_on": "2026-11-23", "ends_on": "2026-12-20", "status": "ACTIVE",
  "participants": [
    { "user_id": 3, "nickname": "민수", "status": "JOINED", "times_per_week": 3, "is_me": true },
    { "user_id": 7, "nickname": "현영", "status": "JOINED", "times_per_week": 2, "is_me": false }
  ],
  "my_checks": ["2026-11-24", "2026-11-26"]
}
```
- 화면 순서(11/19 결정): **"이번 주 N회·누적" 먼저, 연속은 아래**
- 연속 = **목표를 채운 주가 몇 주 연속인지**(`streak_weeks`, 11/19 확정). 이번 주는 진행 중이라 지난주까지로 셈

### 8-10. 완료 체크 (S-12, S-15)
`POST /api/v1/challenges/{id}/checks`
```json
{ "checked_on": "2026-11-19" }
```
- 생략하면 오늘(KST). **오늘·어제만** 가능(제안서 "전날 소급") → 그 밖이면 400
- 이미 있으면 그대로 200 (두 번 눌러도 1번), 새로 만들면 201 — (challenge, user, checked_on) 유니크
- JOINED가 아니거나, 기간(`starts_on`~`ends_on`) 밖이거나, 챌린지가 ACTIVE가 아니면 400
- 응답: `{ "checked_on": "2026-11-19", "this_week": { "checked": 3, "target": 3 } }` → 목표를 채우면 프론트가 "이번 주 목표를 달성했어요!" (REQ-NFR-003 문구 규칙)

`DELETE /api/v1/challenges/{id}/checks/{checked_on}` → 204 (잘못 누른 것 취소, 오늘·어제만)

### 8-11. 함께 채운 칸 `GET /api/v1/challenges/{id}/progress?week_start=2026-11-23`
S-17 · 11/19 결정 "함께 채운 칸 ÷ 전체 칸"
```json
{
  "week_start": "2026-11-23",
  "filled": 4, "total": 5,
  "members": [
    { "nickname": "민수", "is_me": true,  "filled": 3, "target": 3, "checked_days": ["MON", "WED", "FRI"] },
    { "nickname": "현영", "is_me": false, "filled": 1, "target": 2, "checked_days": ["TUE"] }
  ]
}
```
- 사람별 `filled = min(이번 주 체크 수, 개인 목표)` → **목표를 넘긴 체크는 칸에 안 더함**
- `total` = JOINED 참여자 개인 목표의 합. 순위·막대 비교 필드는 두지 않음
- SOLO도 같은 형태(멤버 1명) → 프론트 컴포넌트 하나로 처리

### 8-12. 응원 `POST /api/v1/challenges/{id}/cheers` (P2)
```json
{ "to_user_id": 7, "message": "오늘도 화이팅이에요!" }
```
- 같은 챌린지의 JOINED끼리만, 나에게는 불가
- 같은 사람에게 하루 1번 → 넘으면 429 `"오늘은 이미 응원을 보냈어요."`
- `message` 1~255자. 프리셋 문구는 프론트 상수
- `GET /api/v1/cheers?received=true` → 받은 응원 목록

### 8-13. 대시보드 연결
- 7-3 요약 카드의 `challenge.achievement_rate` = 내 ACTIVE 챌린지들의 `Σ filled ÷ Σ target` (8-11과 같은 계산) → 정할 것 8번 해결안

## 5. 예측·습관 시뮬레이션 — 장성은 (작성 중)
> 3-1·4-1에서 예측을 호출하므로 아래만 맞추면 됨
> - 예측 서비스 함수 시그니처 예: `predict(user, health_profile, checkup_record | None) -> list[RiskPrediction]`
> - 예측 상세 조회(S-09), 시뮬레이션(S-10, 저장 안 함), 최근 예측 조회

## 10. 식단 — `meals`, `foods` (여현지)
S-21(식단 기록), S-22(음식 고르기), S-23(영양 결과) · REQ-FOOD-001~003, NFR-005 · **P2** (식단이 없어도 핵심 흐름은 돌아가야 함, NFR-009)

- 사진 분류는 몇 초 걸려서 **`202 + task_id` → AI 워커 → SSE** (공통 규칙). 나머지는 동기 처리
- 음식 목록은 `foods` 18행 (한 음식에 한 행, 냉면 = 물냉면, 순두부찌개 = 해물). 영양값은 식약처 OpenAPI로 미리 받아 둔 **1인분 값**
- 1차 모델은 18종 중 하나로만 답함. 목록에 없는 음식은 직접 검색(10-8)으로 고름

### 10-1. 사진 올리기 `POST /api/v1/meals` → 202
S-21 · REQ-FOOD-001

**요청** `multipart/form-data`

| 필드 | 규칙 |
|---|---|
| image | 필수. jpg / png / webp, 최대 10MB (제안 → 정할 것 16번). 아니면 400, 크기 초과 413 |
| eaten_at | 선택. 없으면 지금(KST). 지금보다 미래면 400 `"먹은 시간은 지금 이후로 할 수 없어요."` |

**처리 순서**
1. 이미지 저장 → `image_url` (저장 위치는 S3 답변 후 결정, ERD 정할 것)
2. `meals` 저장: `status = PENDING`, `category = MEAL`(1차는 식사만), `portion = 1.0`
3. `TaskMessage(task_type = MEAL_CLASSIFY, user_id, target_id = meals.id)`를 `ai:tasks`에 XADD
4. Redis에 못 넣으면 `status = FAILED`로 두고 응답은 그대로 202 → 사용자가 10-6으로 다시 시도

**응답 202**
```json
{ "meal_id": 101, "task_id": "8f1c2d4e-3b5a-4c6d-9e7f-0a1b2c3d4e5f", "status": "PENDING" }
```

### 10-2. 분류 결과 알림 (SSE)
- 워커 처리: `status = PROCESSING` → 분류 → `candidates`·`model_version` 저장, `COMPLETED` / 3번 실패하면 `FAILED`, `retry_count + 1` → `ai:results`에 발행
- SSE 연결 주소·이벤트 형식은 공통 SSE 명세를 따름 (담당 미정). 식단 결과 `data` 제안:
```json
{ "task_id": "8f1c2d4e-...", "task_type": "MEAL_CLASSIFY", "target_id": 101, "status": "COMPLETED" }
```
- 프론트는 이벤트를 받으면 10-4로 다시 조회. SSE가 끊겼으면 10-4를 몇 초 간격으로 조회해도 됨

### 10-3. 하루 식단 목록 `GET /api/v1/meals?date=2026-11-19`
S-21 · REQ-FOOD-001

- 그날(KST) `eaten_at` 순. 하루 끼니 수가 적어서 커서 없이 전부 줌
- `daily_total`: 그날 **음식을 고른 식단**의 `nutrients` 합 (REQ-FOOD-003 하루 기준 비교에 씀)

**응답 200**
```json
{
  "date": "2026-11-19",
  "items": [
    {
      "id": 101,
      "image_url": "https://.../meals/101.jpg",
      "eaten_at": "2026-11-19T12:30:00+09:00",
      "status": "COMPLETED",
      "food": { "id": 14, "name": "육개장" },
      "portion": 1.0,
      "nutrients": { "kcal": 132.0, "carbs_g": 6.6, "sugar_g": 3.3, "sodium_mg": 884.4, "protein_g": 16.2, "fat_g": 4.4 }
    },
    {
      "id": 102,
      "image_url": "https://.../meals/102.jpg",
      "eaten_at": "2026-11-19T19:10:00+09:00",
      "status": "PROCESSING",
      "food": null,
      "portion": 1.0,
      "nutrients": null
    }
  ],
  "daily_total": { "kcal": 132.0, "carbs_g": 6.6, "sugar_g": 3.3, "sodium_mg": 884.4, "protein_g": 16.2, "fat_g": 4.4 }
}
```

### 10-4. 식단 한 건 `GET /api/v1/meals/{id}` ⚕️
S-22, S-23 · REQ-FOOD-001~003

**응답 200**
```json
{
  "id": 101,
  "image_url": "https://.../meals/101.jpg",
  "eaten_at": "2026-11-19T12:30:00+09:00",
  "category": "MEAL",
  "status": "COMPLETED",
  "retry_count": 0,
  "model_version": "food-cls-v1",
  "candidates": [
    { "food_id": 14, "model_label": "육개장", "name": "육개장", "score": 0.887 },
    { "food_id": 6, "model_label": "닭개장", "name": "육개장_간편조리세트_닭개장", "score": 0.061 },
    { "food_id": 4, "model_label": "김치찌개", "name": "김치찌개", "score": 0.021 },
    { "food_id": 13, "model_label": "순두부찌개", "name": "순두부찌개_해물", "score": 0.012 },
    { "food_id": 3, "model_label": "감자탕", "name": "감자탕", "score": 0.006 }
  ],
  "food": null,
  "portion": 1.0,
  "nutrients": null,
  "feedback": null,
  "created_at": "2026-11-19T12:31:02+09:00",
  "updated_at": "2026-11-19T12:31:05+09:00"
}
```
- `candidates`: `COMPLETED`일 때 확률 높은 순 5개, 그 전·`FAILED`면 null. `score`는 0~1 (소수 셋째 자리)
- `food`: 고르기 전엔 null. 고른 뒤엔 `foods` 행 요약 `{ id, name, model_label, serving_size, serving_unit }`
- 화면은 S-22에서 후보 첫 번째를 미리 선택해 보여 줌 (저장은 10-5에서)
- `feedback`: 음식을 고른 뒤에만 채움 (10-9)

### 10-5. 음식·인분 고르기 `PATCH /api/v1/meals/{id}`
S-22 · REQ-FOOD-001·002
```json
{ "food_id": 14, "portion": 1.5 }
```
| 필드 | 규칙 |
|---|---|
| food_id | `foods`에 있는 id. 없으면 404. 후보 5개 밖의 음식(직접 검색)도 가능 |
| portion | 0.5 / 1.0 / 1.5만. 아니면 422 |
| eaten_at | 선택. 10-1과 같은 규칙 |
| 공통 | 보낸 필드만 바꿈. 음식을 고른 적 없는데 `portion`만 보내면 400 `"음식을 먼저 골라 주세요."` |

- `status`가 `PENDING`·`PROCESSING`이면 **409** `"사진을 분석하고 있어요. 잠시 후 골라 주세요."`
- `FAILED`여도 직접 골라 저장 가능 (C-02 "직접 고르기")
- 저장할 때 `nutrients` = `foods` 1인분 값 × `portion` (소수 첫째 자리 반올림) 스냅샷. 나중에 `foods` 값이 바뀌어도 이 기록은 그대로
- `foods` 영양값이 null인 항목(예: 닭개장 탄수화물·지방)은 `nutrients`에서도 null → 화면은 "정보 없음"
- 응답 200: 10-4와 같은 형식 (`food`·`nutrients`·`feedback` 채워짐)
```json
"nutrients": { "kcal": 198.0, "carbs_g": 9.9, "sugar_g": 5.0, "sodium_mg": 1326.6, "protein_g": 24.3, "fat_g": 6.6 }
```

### 10-6. 다시 분류 `POST /api/v1/meals/{id}/retry` → 202
C-02 · REQ-FOOD-001, NFR-005
- `FAILED`일 때만. 아니면 409 `"다시 분석할 수 없는 상태예요."`
- `status = PENDING`으로 바꾸고 같은 `meals.id`로 새 `TaskMessage` 발행 → 응답 `{ "meal_id", "task_id", "status": "PENDING" }`
- 같은 식단의 재시도 횟수 제한 → 정할 것 18번

### 10-7. 삭제 `DELETE /api/v1/meals/{id}` → 204
- 분석 중에도 삭제 가능. 워커는 `meals` 행이 없으면 건너뛰고 XACK
- 저장한 이미지도 함께 지움

### 10-8. 음식 목록·검색 `GET /api/v1/foods?q=국수`
S-22 "목록에 없어요" · REQ-FOOD-001·002
- `q` 없으면 18행 전부, 있으면 `name`·`model_label` 부분 일치. 18행이라 커서 없이 전부 줌
- 영양값은 **1인분 기준**, `serving_unit`은 `G` / `ML` (18행 중 9행이 mL)

**응답 200**
```json
{
  "items": [
    {
      "id": 15,
      "name": "잔치국수",
      "model_label": "잔치국수",
      "serving_size": 800.0,
      "serving_unit": "ML",
      "kcal": 488.0,
      "carbs_g": 84.6,
      "sugar_g": 6.6,
      "sodium_mg": 2176.0,
      "protein_g": 19.2,
      "fat_g": 6.7
    }
  ]
}
```
- `mfds_code`(식약처 식품코드)는 화면에 안 써서 응답에서 뺌. 화면 출처 표기는 "식약처 식품영양성분DB" 고정 문구
- 식약처 API 실시간 검색은 1차 범위 밖 → 정할 것 19번

### 10-9. 영양 피드백 (10-4·10-5 응답의 `feedback`) ⚕️
S-23 · REQ-FOOD-003
- 질환별 주의 항목: 고혈압 → `sodium_mg`, 당뇨 → `sugar_g`·`carbs_g`. 질환은 최근 설문의 진단 여부 + 최근 예측 결과에서 정함 (3장·5장)
- 이 끼니 값과 그날 누적(10-3 `daily_total`)을 하루 기준량과 비교
```json
"feedback": {
  "focus": ["sodium_mg"],
  "items": [
    { "key": "sodium_mg", "meal_value": 1326.6, "daily_total": 2211.0, "daily_reference": null, "percent": null, "level": null }
  ]
}
```
- **하루 기준량·판단 기준(`level` 값)은 미정** → 정할 것 17번. 정하기 전엔 `daily_reference`·`percent`·`level`을 null로 두고 값만 보여 줌
- "다음 끼니에 바꿀 한 가지"(S-23 아래쪽)는 LLM 추천(REQ-LLM-002, 김민준) 쪽 API

## 2·11. 인증·회원 / LLM 추천 / 알림
> 담당 정해지면 채움

---

## 9. 정할 것
| # | 내용 | 제안 | 누구랑 |
|---|---|---|---|
| 1 | 마이(S-27)에서 키·가족력 등 "안 묻는 문항" 수정 방법 | 새 kind `EDIT` 추가 없이, WEEKLY 전체 모드(모든 문항 받음)로 새 행 저장. 또는 enum에 `EDIT` 추가 | ERD(김지연·이지희) |
| 2 | 검진 기록 삭제 시 예측 행 처리 | `risk_predictions.checkup_record_id` FK `ON DELETE SET NULL` (스냅샷이 있어서 이력은 남음) | ERD |
| 3 | 일일 기록 값 규칙(6-0 위쪽 7종) | 위 표대로 ERD Note에 추가 | ERD·프론트 |
| 4 | 건강 기록 수정 허용 여부 | 허용하려면 `health_logs.updated_at` 추가, 아니면 삭제 후 재입력 | ERD |
| 5 | 주간 재설문 하루·주 몇 번까지 | 같은 주에 여러 번 해도 새 행(이력 보존), 추이는 주의 마지막 값만 사용 (7-1) | 예측(장성은) |
| 6 | 예측 실패 시 설문 저장 여부 | 설문은 저장, `prediction_error: true` 후 재시도 버튼 (3-1) | 예측(장성은) |
| 7 | 설문 문항 정의 API(3-6) 할지 | P2. 처음엔 프론트 상수 | 프론트(김지연·여현지) |
| 8 | 대시보드 챌린지 달성률 계산식 | 8-13: Σ min(체크, 개인 목표) ÷ Σ 개인 목표 | 챌린지 담당 |
| 9 | 검진 수치가 있을 때 판정 | ✅ 11/19 데이터팀 결정: 모델 점수 행 항상 + 기준표 행 추가, 추이는 모델 점수. 남은 것(검진 유효기간, 수치 일부만 있을 때 규칙)은 **장성은님이 5장 작성하며 정리해 별도 PR** | 장성은 |
| 10 | 서비스 방향(보건소·보험사 기관 화면)이 채택되면 계정 역할·권한 | 보험사 역할은 API에서 달성 여부만 내려주도록 막음 (화면이 아니라 서버에서) | 전원 |
| 11 | `challenge_templates.category` 값 | ✅ 11/19 확정: 대문자 7종 (ERD PR에서 반영) | — |
| 12 | 짝꿍 끊기·호스트 나가기 | ✅ 11/19 확정 → 8-6·8-8. 호스트 넘기기는 1:N만, 1:1은 남은 사람이 고르기. `created_by` = 현재 호스트 (컬럼 추가 없음) | — |
| 13 | "연속" 기준 | ✅ 11/19 확정: 목표 채운 주 연속 (8-9) | — |
| 14 | 체중 챌린지 체크와 체중 기록 연결 | 체중 기록(`health_logs` WEIGHT)을 남기면 그날 체중 챌린지 자동 체크 (수치는 짝꿍에게 안 감) — 선택 | 백엔드 |
| 15 | 초대 링크 만료 | ✅ 11/19 확정: created_at 기준 7일 (8-2~8-4) | — |
| 16 | 식단 사진 형식·크기 | jpg / png / webp, 최대 10MB. 아이폰 HEIC는 프론트에서 jpg로 바꿔 올림 | 프론트(김지연)·백엔드 |
| 17 | 식단 피드백 하루 기준량·판단 기준 (10-9) | 나트륨·당류·탄수화물 하루 기준량과 출처, 끼니 단위 vs 하루 누적 → 여현지가 정해 requirements REQ-FOOD-003에 기록 | 여현지 |
| 18 | 식단 재분류 횟수 제한 (10-6) | 같은 식단 하루 3번까지, 넘으면 429 `"다시 분석은 3번까지 할 수 있어요. 직접 골라 주세요."` | 워커 담당 |
| 19 | 목록에 없는 음식 (10-8) | 1차는 `foods` 18행 안에서만 검색. 식약처 API 실시간 검색은 호출 한도·캐시 문제로 S5 이후 검토 | 여현지·백엔드 |
| 20 | 공통 SSE 명세 | 식단·LLM·OCR 결과를 같은 SSE 연결로 보낼지, 이벤트 이름·`data` 형식 (10-2 제안) | 워커·LLM 담당 |
| 21 | 식단 비전 LLM 보조 (REQ-FOOD-001) | 쓸지 여부, top-1 확률 기준, 18종 밖 음식 처리. 쓰면 10-2 워커 처리 안에서 호출(새 API 없음) | 여현지·LLM(김민준) |