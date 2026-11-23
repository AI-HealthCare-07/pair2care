# API 명세서 (v1 확정)

> 상태: **v1 확정** — 11/20 4종(요구사항·와이어프레임·ERD·API) 교차 확인 후 확정. 이후 변경은 PR로 하고 관련 문서도 같이 고침. 9장 '정할 것'의 남은 항목은 결정되는 대로 반영함  

> 기준: [erd.dbml](erd.dbml) · [survey-mapping.md](survey-mapping.md) · [requirements.md](requirements.md) · [wireframe.md](wireframe.md) (2026-11-19 develop 기준)
> 담당: 1·3·4·6·7장 최현영 · 8장 이지희 (초안 최현영) · 2·12장 김지연 · 5장 명세·학습 장성은 / 서빙 구현 최현영 · 10장 여현지 · 11장 김민준 (장마다 제목에도 표기)
> ⚕️ 표시 응답은 화면에 의료 안내 문구(C-01)를 붙임 (REQ-NFR-001)

## 0. 목차
1. 공통 규칙
2. **인증·회원** — 김지연
3. **건강 프로필(설문)** — 최현영
4. **검진 수치** — 최현영
5. **예측·습관 시뮬레이션** — 명세·학습 장성은 / 서빙 구현 최현영
6. **건강 기록** — 최현영
7. **대시보드** — 최현영
8. **챌린지·짝꿍** — 이지희 (11/20 담당 확정, 초안 최현영 · 11/19 PR #30·#31 반영)
10. **식단** — 여현지
11. **LLM 추천** — 김민준
12. **알림 (+ 공통 SSE)** — 김지연
9. 정할 것 (맨 끝에 둠, 장마다 생긴 미결 항목을 한 표로 모음)

---

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 주소 | `/api/v1` (기존 `v1_routers` 그대로) |
| 인증 | `Authorization: Bearer <access_token>`. 아래 예외를 빼고 모두 로그인 필요 → 없거나 만료되면 401<br>**예외(로그인 없이)**: 회원가입 2-1, 로그인 2-2, 토큰 갱신 2-3(refresh 쿠키로 판단), 비밀번호 찾기 2-7<br>SSE(12-6)는 헤더 대신 1회용 티켓(`?ticket=`)으로 인증 |
| 내 데이터만 | 경로에 `user_id`를 받지 않음. 토큰의 사용자 기준으로만 읽고 씀. 남의 리소스 id로 접근하면 **404** (존재 여부를 숨김) |
| 필드 이름 | 요청·응답 JSON은 **ERD 컬럼 이름 그대로** snake_case |
| enum | ERD와 같은 대문자 (`ONBOARDING`, `HYPERTENSION`, `BLOOD_PRESSURE` …) |
| 시간 | ISO 8601 + KST 오프셋. datetime `2026-11-19T09:30:00+09:00`, date `2026-11-19`, 하루 중 시각(알림·리마인더·방해 금지) `HH:MM` 24시간제 `19:00` |
| 숫자 | decimal 컬럼(체중·허리둘레·기록 값)은 JSON number로 주고받음 (소수 둘째 자리까지) |
| 목록 | `?limit=20&cursor=<마지막 id>` 커서 방식, 최신순. 응답 `{ "items": [...], "next_cursor": 123 \| null }` |
| 에러 | 기존 코드처럼 FastAPI 기본 형식 `{ "detail": "한국어 메시지" }`. 입력 검사 실패는 FastAPI 기본 422 (`detail`이 배열)<br>**프론트가 종류로 갈라 처리해야 하는 에러에만** `code`를 붙임: `{ "detail": "한국어 메시지", "code": "SURVEY_VERSION_MISMATCH" }` → 프론트는 문구 글자가 아니라 `code`로 분기 (문구는 바뀔 수 있음)<br>구현: `app/core/exceptions.py`의 `AppError` + 전용 핸들러 (`HTTPException(detail={...})`는 `detail`이 한 번 더 감싸져서 쓰지 않음). `code` 목록은 아래 표와 `ErrorCode`를 같이 고침 |
| 에러 code 목록 | `SURVEY_VERSION_MISMATCH` 409 (3-1, 설문 버전 다름 → 3-6 다시 불러오기) · `ONBOARDING_REQUIRED` 409 (3-1, 가입 설문 없이 WEEKLY → S-06) · `ONBOARDING_ALREADY_DONE` 409 (3-1, 가입 설문 두 번 → 홈) · `SURVEY_FIELD_INVALID` 400 (3-1 문항 규칙 위반, `field`에 문항 이름 → 그 문항으로 이동) |
| 상태 코드 | 200 조회·수정 / 201 생성 / 204 삭제 / 400 규칙 위반 / 401 인증 / 404 없음 / 403 권한 없음(예: 호스트만 가능) / 409 중복·순서 충돌 / 410 만료(예: 초대 링크 7일) / 422 형식 오류 / 429 횟수 제한(예: 응원 하루 1번) |
| 로그 | 요청·응답 본문의 건강 수치는 서버 로그에 남기지 않음 (REQ-NFR-006) |
| 오래 걸리는 작업 | LLM·식단 사진·결과지 OCR은 `202 + task_id` (AI 워커 TaskMessage·SSE와 같은 이름) → Redis Stream 워커 → 공통 SSE(12-6)의 `event: task`로 결과 알림 → 프론트가 해당 조회 API로 다시 가져옴 (REQ-NFR-005). 결과 내용은 이벤트에 넣지 않음 |

---

## 2. 인증·회원 — `users`, `user_consents` (김지연)
S-01~S-05, S-27 · REQ-USER-001~005

### 2-0. 기존 코드와 바꿀 점 (S2 구현 때)
명세는 ERD 기준(1장 "필드 이름 = ERD 컬럼"). 지금 코드(`app/apis/v1/auth_routers.py`·`user_routers.py`, `app/dtos/`)와 다른 곳
| 항목 | 지금 코드 | 바꿀 것 |
|---|---|---|
| 닉네임 | `name` (20자) | `nickname` (ERD varchar(50), 화면은 2~20자) |
| 휴대폰 번호 | `phone_number` 필수 | 삭제 (11/17 결정, REQ-USER-001) |
| 생년월일 | 가입 `birth_date` / 수정 `birthday` | `birthday` 하나로 |
| 이메일 길이 | 최대 40자 | 최대 255자 (ERD) |
| 회원가입 응답 | `{"detail": "회원가입이 성공적으로 완료되었습니다."}` | 2-1처럼 토큰 + 회원 요약 |
| 토큰 갱신 | `GET /auth/token/refresh` | `POST` (상태를 바꾸는 요청) |
| 로그아웃 | 없음 | 2-4 추가 |
| 약관 동의 | 없음 | 가입 요청에 같이 받음 (2-1), 2-6 추가 |
| 비밀번호 규칙 | 8자 이상 + 대·소문자·숫자·특수문자 각 1개 (`validate_password`) | **8자 이상 + 영문·숫자·특수문자 각 1개 이상** (11/20 변경. 11/19엔 가입 부담을 줄이려고 영문·숫자만 받기로 했으나 보안을 위해 특수문자 추가, 대·소문자 구분은 안 함) |
| 로그인 실패 잠금 | 없음 | 2-2: 5번 틀리면 10분 잠금 |
- 그대로 쓰는 것: 만 14세 미만 가입 불가(`validate_birthday`), access 토큰은 본문 / refresh 토큰은 httpOnly 쿠키

### 2-1. 회원가입 `POST /api/v1/auth/signup` → 201
S-02, S-03 · REQ-USER-001·005 · 로그인 필요 없음
```json
{
  "email": "minsu@example.com",
  "password": "Pair2care!",
  "nickname": "민수",
  "gender": "MALE",
  "birthday": "1972-03-15",
  "consents": [
    { "agreement": "TERMS", "version": "v1.0", "is_agreed": true },
    { "agreement": "PRIVACY", "version": "v1.0", "is_agreed": true },
    { "agreement": "SENSITIVE_HEALTH", "version": "v1.0", "is_agreed": true }
  ]
}
```
| 필드 | 규칙 |
|---|---|
| email | 이메일 형식, 최대 255자. 이미 있으면 **409** `"이미 가입된 이메일이에요."` |
| password | 8자 이상, 영문·숫자·특수문자 각 1개 이상. 특수문자는 키보드 기호(ASCII 문장부호 `!@#$%^&*` 등 32자), 공백·한글은 안 됨. 아니면 422. 화면은 칸 아래 안내 문구 "8자 이상, 영문+숫자+특수문자(!@#$ 등)"로 미리 알려 줌 (체크 목록 없음, S-02) |
| nickname | 2~20자. 중복 허용 (짝꿍 화면엔 닉네임만 보여서 같은 이름이 있어도 됨) |
| gender | `MALE` / `FEMALE` (예측 입력 sex, 설문 임신 문항, 대사증후군 기준에 씀) |
| birthday | 만 14세 미만이면 400 `"만 14세 미만은 가입할 수 없어요."` |
| consents | **3종 모두 `is_agreed: true` 필수**, `version`은 서버의 현재 약관 버전과 같아야 함. 아니면 400 `"필수 약관에 모두 동의해 주세요."` → 정할 것 22번 |

**처리 (한 트랜잭션)**: `users` 저장 → `user_consents` 3행 저장(`created_at` = 동의 시각) → 토큰 발급
- 동의는 화면 S-03에서 받지만 저장은 가입과 한 번에 (동의 없이 가입만 된 계정이 생기지 않게)

**응답 201** (바로 S-06 설문으로 넘어가도록 로그인 상태로 줌, refresh 토큰은 쿠키)
```json
{
  "access_token": "eyJ...",
  "user": { "id": 3, "email": "minsu@example.com", "nickname": "민수", "gender": "MALE", "birthday": "1972-03-15", "created_at": "2026-11-19T10:00:00+09:00" },
  "has_health_profile": false
}
```
- `has_health_profile`: 가입 설문(ONBOARDING)을 했는지 → 프론트가 S-06으로 보낼지 결정 (로그인 응답에도 같은 값)

### 2-2. 로그인 `POST /api/v1/auth/login` → 200
S-04 · REQ-USER-002 · 로그인 필요 없음
```json
{ "email": "minsu@example.com", "password": "Pair2care!" }
```
- 응답: `{ "access_token": "...", "has_health_profile": true }` + refresh 토큰 httpOnly 쿠키 (`Secure`는 운영만)
- 이메일이 없거나 비밀번호가 틀리거나 탈퇴한 계정(`is_active = false`)이면 모두 **401** `"이메일 또는 비밀번호가 맞지 않아요."` (어느 쪽이 틀렸는지 알려 주면 가입된 이메일을 알아낼 수 있어서 같은 문구)
- 성공 시 `users.last_login` 갱신
- **5번 틀리면 10분 잠금**: 이메일별 실패 횟수를 Redis에 10분 저장, 5번째 실패부터 그 이메일은 10분 동안 **429** `"로그인을 5번 틀려서 10분 뒤에 다시 시도할 수 있어요."`. 성공하면 횟수 초기화
  - 가입 안 된 이메일도 똑같이 셈 (잠금 여부로 가입된 이메일을 알아낼 수 없게)
  - 화면은 401 문구 아래 "(5회 틀리면 10분 잠금)"을 같이 보여 줌 (S-04)
- 토큰 유효 시간은 기존 설정 그대로 (`config`의 access·refresh 만료값)

### 2-3. 토큰 갱신 `POST /api/v1/auth/token/refresh` → 200
- 요청 본문 없음, refresh 토큰 쿠키로 판단. 응답 `{ "access_token": "..." }`
- 쿠키가 없거나 만료·위조면 **401** `"다시 로그인해 주세요."` → 프론트는 S-04로
- 프론트는 API가 401을 주면 한 번 갱신하고 원래 요청을 다시 보냄 (갱신도 401이면 로그아웃 처리)

### 2-4. 로그아웃 `POST /api/v1/auth/logout` → 204
- refresh 토큰 쿠키 삭제
- 요청에 `push_endpoint`가 있으면 그 기기의 웹 푸시 구독도 삭제 (ERD `push_subscriptions` Note "로그아웃 시 그 기기 구독 삭제", 12-5)
```json
{ "push_endpoint": "https://fcm.googleapis.com/fcm/send/..." }
```
- access 토큰은 서버에서 막지 않음(블랙리스트 없음) → 만료 시간 30분으로 대신 (정할 것 23번, 11/23 확정). 로그아웃 뒤에도 이미 발급한 access 토큰은 최대 30분 살아 있음

### 2-5. 내 정보 `GET /api/v1/users/me` · `PATCH /api/v1/users/me`
S-27 · REQ-USER-003
**GET 응답 200**
```json
{ "id": 3, "email": "minsu@example.com", "nickname": "민수", "gender": "MALE", "birthday": "1972-03-15", "has_health_profile": true, "created_at": "2026-11-19T10:00:00+09:00" }
```
**PATCH** `{ "nickname": "민수아빠" }`
- 바꿀 수 있는 건 **`nickname`만** (2~20자)
- `email`: 로그인 아이디라 바꾸지 않음 (1차)
- `gender`·`birthday`: 예측 입력(성별·나이)이라 바꾸면 지난 예측과 기준이 달라짐 → 사용자는 직접 수정 불가, 보내면 400 `"성별·생년월일은 바꿀 수 없어요. 고치려면 관리자에게 요청해 주세요."` 잘못 넣은 경우 관리자에게 요청해 관리자가 고침 (11/20 확정, 정할 것 24번)
- 방해 금지 시간(`quiet_start`·`quiet_end`)은 `users` 컬럼이지만 12-2 알림 설정에서 다룸
- 설문·검진 수정은 3·4장 API (S-27은 입구만)

**비밀번호 변경** `PATCH /api/v1/users/me/password` → 204
```json
{ "current_password": "Pair2care!", "new_password": "Pair2care!!" }
```
- 현재 비밀번호가 틀리면 400 `"현재 비밀번호가 맞지 않아요."`, 새 비밀번호는 2-1 규칙

### 2-6. 약관 동의 `GET /api/v1/users/me/consents` · `POST /api/v1/users/me/consents`
S-27 "동의 내역" · REQ-USER-005
- `user_consents`는 동의·철회할 때마다 새 행을 쌓고, 현재 상태는 종류별 최신 행
**GET 응답 200** (종류별 최신 상태 + 지금 약관 버전)
```json
{
  "items": [
    { "agreement": "TERMS", "version": "v1.0", "is_agreed": true, "agreed_at": "2026-11-19T10:00:00+09:00", "current_version": "v1.0" },
    { "agreement": "PRIVACY", "version": "v1.0", "is_agreed": true, "agreed_at": "2026-11-19T10:00:00+09:00", "current_version": "v1.0" },
    { "agreement": "SENSITIVE_HEALTH", "version": "v1.0", "is_agreed": true, "agreed_at": "2026-11-19T10:00:00+09:00", "current_version": "v1.0" }
  ],
  "needs_reconsent": false
}
```
- `needs_reconsent`: 약관 버전이 올라가서 다시 동의가 필요하면 true → 프론트가 동의 화면을 띄움
**POST** (새 버전 재동의) `{ "agreement": "PRIVACY", "version": "v1.1", "is_agreed": true }` → 201
- 3종 모두 필수라서 **철회(`is_agreed: false`)는 여기서 받지 않고 탈퇴(2-8)로 안내** → 400 `"필수 동의는 철회할 수 없어요. 탈퇴로 진행해 주세요."` → 정할 것 22번
- 약관 문구는 정적 페이지, 버전은 서버 상수

### 2-7. 비밀번호 찾기 (P2)
S-05 (Figma M15·M16) · REQ-USER-004 · 로그인 필요 없음 · **이메일 인증번호 방식** (11/19 확정, 정할 것 25번)
1. `POST /api/v1/auth/password-reset` `{ "email": "..." }` → **항상 202** `"가입된 이메일이면 인증번호를 보냈어요."` (가입 여부를 알려 주지 않음)
   - 가입된 이메일이면 6자리 숫자 인증번호(`secrets.randbelow`)를 **Redis에 10분**(테이블 없음, ERD 결정) 저장하고 메일 발송
   - 메일 제목에도 번호를 넣음 → 알림만 보고도 확인 가능
   - 같은 이메일 요청은 1분에 1번 → 넘으면 429 `"잠시 후 다시 시도해 주세요."`. 다시 요청하면 이전 번호는 폐기
2. `POST /api/v1/auth/password-reset/confirm` `{ "email": "...", "code": "123456", "new_password": "..." }` → 204
   - 번호가 없거나 10분이 지났으면 **410** `"인증번호가 만료됐어요. 다시 요청해 주세요."`
   - 번호가 틀리면 400 `"인증번호가 맞지 않아요."`, **5번 틀리면 번호 폐기** → 429 `"인증번호를 다시 요청해 주세요."` (6자리라 맞혀 보기 막음)
   - 맞으면 비밀번호 변경 후 번호 바로 삭제(1회용). 새 비밀번호는 2-1 규칙
   - 비밀번호를 바꾸면 그 사용자의 refresh 토큰은 무효 처리하지 않음(블랙리스트 없음, 2-4와 같음)
- 링크 방식 대신 인증번호를 고른 이유: 모바일 PWA가 기본인데, 아이폰 홈 화면 앱에서 메일 링크를 누르면 사파리로 열려 흐름이 끊김. 번호는 앱 안에서 끝남
- 화면: 번호 칸은 붙여넣기 가능(6자리 한 번에)
- 메일 발송 방법(SMTP·외부 서비스)은 구현 때 결정 (REQ-USER-004)

### 2-8. 탈퇴 `DELETE /api/v1/users/me` → 204
S-27 · REQ-USER-003
```json
{ "password": "Pair2care!" }
```
- 비밀번호 확인 (틀리면 400)
- **처리 (한 트랜잭션)**
  1. 짝꿍 관계는 8-6 "끊기"와 같이 처리 (모든 짝꿍 ENDED, 1:1 챌린지는 상대가 "종료 / 혼자 계속" 고르기, 1:N은 LEFT + 호스트 넘기기)
  2. 건강 정보(`health_profiles`·`checkup_records`·`risk_predictions`·`health_logs`·`meals`·`recommendations`)와 알림·푸시 구독·리마인더 **즉시 삭제**
  3. `users`는 `is_active = false`, 이메일·닉네임을 지워서(예: `deleted_3@invalid`, "탈퇴한 사용자") 같은 이메일로 다시 가입 가능하게 함. 상대에게 남는 체크·응원 기록은 "탈퇴한 사용자"로 보임
- 삭제 범위·보관 기간은 개인정보 처리방침과 맞춰야 함 → 정할 것 26번
- 응답 뒤 refresh 쿠키 삭제

---

## 3. 건강 프로필 (설문) — `health_profiles`

설문 한 번 = 한 행. 가입 설문(`ONBOARDING`)과 주간 재설문(`WEEKLY`)이 같은 API를 씀.

### 3-1. 설문 저장 `POST /api/v1/health-profiles` ⚕️
S-06(가입 설문), S-11(주간 재설문 앞부분) · REQ-PROF-001, PRED-004

**요청**
```json
{
  "kind": "ONBOARDING",
  "survey_version": "v1.0",
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
| weight_kg | 25.0~300.0 (일일 기록 체중과 같게, 11/23) | 필수 | 필수 |
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
| is_pregnant | 여성: true / false 필수, 남성: null (보내면 400) | 필수(여성) | 필수(여성) |

**건너뛰기 처리 (서버가 채움)**
- 화면에서 건너뛴 문항은 클라이언트가 `null`로 보내고, **비해당 코드(8 / 888)는 서버가 채움**. 건너뛰기로 생기는 8·888은 클라이언트가 직접 보내지 않음 (11/23 7번 결정)
  - 건너뛰기로 서버가 채움 (프론트는 null): 11·12·13번 → 8, 15번 → 8, 16번 → 888. 프론트가 이 8·888을 직접 보내면 모두 보기 범위 밖이라 **422**
  - 사용자가 고른 보기라 **그대로 보냄**: 6·9번 형제자매 없음 `8`, 17·18번 사용한 적 없음 `8`, 11번 전혀 `1`, 15번 지금은 안 피움 `3`
  - `alcohol_ever = 1` → alcohol_frequency·alcohol_amount·binge_frequency = 8
  - `alcohol_frequency = 1` → alcohol_amount·binge_frequency = 8
  - `smoking_lifetime = 3` → smoking_current = 8, cigarettes_per_day = 888
  - `smoking_current = 3` → cigarettes_per_day = 888
- 건너뛸 조건인데 값을 보냄(예: `alcohol_ever = 1`인데 `alcohol_frequency = 4`) → **400** `"술을 마셔 본 적이 없으면 음주 횟수는 보낼 수 없어요."` (서버가 조용히 덮어쓰지 않음, 프론트 버그를 드러내기 위함)
- 해당자인데 값이 빠짐(예: `alcohol_frequency = 5`인데 `alcohol_amount = null`) → **400** `"한 번에 마시는 양을 골라 주세요."`
- 문항별 전체 문구·검사 순서(형식 422 → 버전·순서 409 → 성별 400 → 문항 번호 순 400, 첫 에러 하나만)는 3-1 구현 PR에서 코드 상수와 같이 정리 (11/23 최현영 목록)
- **400에는 어느 문항인지 `field`를 같이 줌** → 프론트가 문구를 해석하지 않고 그 문항으로 이동 (11/23 여현지 리뷰)
  ```json
  { "detail": "한 번에 마시는 양을 골라 주세요.", "code": "SURVEY_FIELD_INVALID", "field": "alcohol_amount" }
  ```
  - 성별 조건(21번) 400도 같은 모양, `field: "is_pregnant"`. `code`·`field`는 1장 `AppError` 규칙으로 내려줌 (3-1 구현 때 `field` 추가)
- WEEKLY의 `binge_frequency`·`cigarettes_per_day` (survey-mapping.md 재설문 규칙): 직전에 비해당(8 / 888)이었는데 이번 답으로 해당되면(예: 비흡연 → 매일 흡연) 다시 받음 → 빠지면 400. 이번 답으로 비해당이 되면 8 / 888 자동 저장. 그 외엔 직전 값 복사
  - 프론트는 직전 값을 따로 조회하지 않고, 3-6 `kind=WEEKLY` 응답의 `ask_when_applicable`로 다시 물을지 앎
  - `ask_when_applicable: false`인 문항에 값이 오면: 이번 답으로 해당이면 **무시하고 직전 값 복사**(안 묻는 문항과 같음), 이번 답으로 비해당이면 건너뛰기 위반이라 **400**. 판단은 요청에 온 플래그가 아니라 **서버가 직전 행으로 다시** 함 (11/23 최현영 리뷰)
- 나이는 이 행의 `created_at`(KST) 기준 만 나이로 계산 (survey-mapping.md)

**공통 규칙**
- `survey_version`이 서버의 현재 버전과 다르면 **409** `code: SURVEY_VERSION_MISMATCH` `"설문 문항이 바뀌었어요. 다시 불러올게요."` → 프론트가 3-6을 다시 받아 화면을 새로 그림 (11/23 7번 결정)
- 409 세 가지는 프론트 처리가 달라서 문구가 아니라 `code`로 가름 (1장 에러 code 목록)

**WEEKLY 추가 규칙**
- ONBOARDING 행이 없으면 **409** `code: ONBOARDING_REQUIRED` `"가입 설문을 먼저 해 주세요."` → S-06으로
- ONBOARDING을 두 번 보내면 **409** `code: ONBOARDING_ALREADY_DONE` → 홈으로 `"가입 설문은 이미 했어요. 바뀐 내용은 주간 설문에서 알려 주세요."` (수정은 3-4 참고)
- 안 묻는 문항은 클라이언트가 보내도 무시하고 직전 행에서 복사 (위 표)

**처리 순서 (한 트랜잭션)**
1. 검사 → 건너뛰기 코드 채움 → (WEEKLY) 직전 값 복사 → `health_profiles` 저장
2. 예측 서비스 호출 (FastAPI 안에서 바로 추론, REQ-PRED-001) → 질환별 `risk_predictions` 저장. 진단 "예"인 질환은 예측 행을 만들지 않음. **`is_pregnant = true`면 두 질환 모두 예측 안 함** (모델이 임신부를 빼고 학습)
   - 유효한 검진 수치가 있으면 같은 질환에 **모델 점수 행(MODEL) + 기준표 판정 행(CHECKUP_CRITERIA) 둘 다** 저장 (11/19 데이터팀 ERD 요청 ②)
3. 예측 실패 시 설문은 저장하고 응답의 `predictions`를 빈 배열 + `prediction_error: true`로 줌 (설문을 다시 받게 하지 않기 위함)

> 2번 예측 호출의 세부(입력 변환·검진 수치 기준표·응답 상세)는 **5장 예측 API(명세·학습 장성은 / 서빙 구현 최현영)** 와 맞춤

**응답 201**
```json
{
  "health_profile": {
    "id": 31,
    "kind": "ONBOARDING",
    "survey_version": "v1.0",
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
S-06, S-11 · 로그인 필요 · **11/23 7번 결정으로 확정 (P2 아님)**
- 문항 문구·보기·저장값·건너뛰기 조건의 **기준은 서버 상수 한 곳**, 이 API가 그대로 내려줌 → 학습 코드(survey-mapping.md)와 어긋나지 않게
- 프론트는 같은 JSON 모양 상수로 먼저 시작하고, **S-11(주간 재설문) 구현 전에 이 API fetch로 바꿈** (그전까지 규칙이 두 곳이라 오래 두지 않음)
- 대응표 코드가 바뀌면 `survey-mapping.md` + 서버 상수를 **같은 PR**에서 고치고 `survey_version`을 올림 (형식은 ERD와 같은 `v1.0` → `v1.1`, 409 비교는 문자열 그대로)
- 담당: 문항 정의 내용 장성은(대응표 담당) / 서버 상수 위치·3-1 검사·건너뛰기 로직은 3-1 구현 담당과 함께

**문항 타입**
| type | 쓰는 문항 | 추가 필드 |
|---|---|---|
| `SINGLE` | 가족력·음주·흡연 등 보기 고르기 | `options: [{label, value}]` |
| `NUMBER` | 키·몸무게·허리둘레·하루 흡연량 | `min`, `max`, `unit`, `step`, `required` (범위는 3-1 입력 규칙 표와 같은 값) |
| `BOOLEAN` | 고혈압·당뇨 진단, 임신 | `options: [{"label": "예", "value": true}, {"label": "아니요", "value": false}]` — 다른 타입처럼 **서버가 내려줌** (프론트 고정값 없음) |

**공통 필드**
- `skip`: `[{when, fields}]` — 이 문항 값이 `when`이면 `fields` 문항은 화면에서 건너뛰고 null로 보냄 (3-1 건너뛰기 처리와 같은 규칙)
- `only_for`: `"FEMALE"` 등 성별 조건. 없으면 모두에게 물음 (예: `is_pregnant`)
- `text`: 기본 문구 (모든 문항에 있음). `text_by_gender`: 성별마다 문구가 다를 때 `{ "MALE": "...", "FEMALE": "..." }` → 사용자 성별 값이 있으면 이걸, 없으면 `text`를 씀 (예: 13번 폭음 남 7잔 / 여 5잔)
- **사용자 성별은 `users.gender`** (`"MALE"` / `"FEMALE"`): 가입 응답(2-1)의 `user.gender` 또는 내 정보 `GET /api/v1/users/me`(2-5)의 `gender`로 받음. `only_for`·`text_by_gender`의 키와 같은 값
- `ask_when_applicable` (**`kind=WEEKLY`에서만**): 서버가 사용자의 직전 행을 보고 채움. `true`면 직전에 비해당(8 / 888)이었다는 뜻 → 이번 답으로 해당되면 물음. `false`면 해당돼도 묻지 않음(서버가 직전 값 복사). 13·16번에만 붙음 → 직전 프로필 조회 API는 따로 만들지 않음
- 가입 설문(ONBOARDING) 없이 `kind=WEEKLY`를 부르면 직전 행이 없어 `ask_when_applicable`을 못 채움 → 3-1과 같은 **409** `code: ONBOARDING_REQUIRED` `"가입 설문을 먼저 해 주세요."` (프론트는 같은 code로 S-06 이동)
- WEEKLY는 재설문에서 묻는 문항만 내려줌 (survey-mapping.md "재설문: 물음"). 응답이 사용자마다 달라서(`ask_when_applicable`) **캐시하지 않음**, ONBOARDING은 `survey_version`이 같으면 캐시해도 됨
- `questions` 배열 순서 = 화면 순서, `options` 배열 순서 = 보기 순서
- 필수 여부: 11·12·13·15·16번은 상위 답에 따라 묻는 조건부 문항이라 `skip`으로 정해짐 (`required`는 NUMBER에만)

```json
{
  "survey_version": "v1.0",
  "kind": "WEEKLY",
  "questions": [
    { "no": 2, "field": "weight_kg", "text": "몸무게를 알려 주세요.",
      "type": "NUMBER", "min": 25.0, "max": 300.0, "step": 0.1, "unit": "kg", "required": true },
    { "no": 10, "field": "alcohol_ever", "text": "지금까지 술을 마셔 본 적이 있나요?",
      "type": "SINGLE", "options": [{"label": "없다", "value": 1}, {"label": "있다", "value": 2}],
      "skip": [{"when": 1, "fields": ["alcohol_frequency", "alcohol_amount", "binge_frequency"]}] },
    { "no": 13, "field": "binge_frequency",
      "text": "한 번에 많이 마시는 날이 얼마나 되나요?",
      "text_by_gender": { "MALE": "한 번에 7잔 이상 마시는 날이 얼마나 되나요?", "FEMALE": "한 번에 5잔 이상 마시는 날이 얼마나 되나요?" },
      "type": "SINGLE", "options": [{"label": "전혀 없음", "value": 1}, "..."], "ask_when_applicable": true },
    { "no": 21, "field": "is_pregnant", "text": "지금 임신 중인가요?", "type": "BOOLEAN", "only_for": "FEMALE",
      "options": [{"label": "예", "value": true}, {"label": "아니요", "value": false}] }
  ]
}
```
- 문구·보기는 예시. 실제 내용은 survey-mapping.md 기준으로 장성은이 채움

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
## 5. 예측·습관 시뮬레이션 — 명세·학습 장성은 / 서빙 구현 최현영
S-09(예측 결과), S-10(습관 시뮬레이션) · REQ-PRED-001~004 · 근거: 데이터셋 진행 상황, survey-mapping.md, erd.dbml
> 모든 응답은 "위험도 참고값". "진단", "발병 확정" 표현 금지 (C-01)

### 5-0. 예측 서비스 (API 아님, 3-1·4-1·4-4에서 호출)
`predict(user, health_profile, checkup_record | None) -> list[RiskPrediction]`

**처리 순서**
1. 나이(`health_profile.created_at` 기준 만 나이)가 30~69세 밖 → 두 질환 모두 행 없음, `skipped_reason = AGE_OUT_OF_RANGE`
2. `is_pregnant = true` → 두 질환 모두 행 없음, `skipped_reason = PREGNANT`
3. 진단 "예"인 질환 → 행 없음, `managed_diseases`에 넣음
4. 나머지 질환 → 모델 행(`MODEL`) 저장
5. 유효한 검진 수치로 판정이 되면 같은 질환에 기준표 행(`CHECKUP_CRITERIA`) 추가 저장 (5-1)

**모델 행 (`method = MODEL`)**
| 필드 | 규칙 |
|---|---|
| score | 모델 확률 × 100, 반올림 정수 0~100 |
| level | `LOW` / `CAUTION` / `HIGH`. 기준값은 학습 후 점수 분포로 정함 (12/4 전) |
| factors | 상위 3개 `[{"feature": "weight_kg", "direction": "UP"}]`. 로지스틱 계수 × (사용자 값 − 학습 데이터 평균)의 절댓값 상위 3개, 양수 `UP` / 음수 `DOWN`. 학습 평균은 모델과 같이 MLflow에 저장. 최종 모델이 로지스틱이 아니면(HistGB 등) SHAP 값 상위 3개로 바꿈 (응답 형식은 같음) |
| model_version | MLflow 등록 이름:버전 (`diabetes_risk:v1`, `hypertension_risk:v1`) |
| checkup_record_id | null |
| input_snapshot | 모델에 실제로 넣은 값 (변환 후). 예측 이력·"바뀐 입력값" 비교용 |

**입력 변환**
- 모델 입력 13개: sex, age, 키, 몸무게, 가족력 6개, alcohol_frequency, alcohol_amount, smoking_current
- 변환은 학습 전처리와 같은 함수를 씀 (학습·서빙 따로 짜지 않음)
- 키·몸무게를 그대로 넣을지 BMI로 넣을지, 가족력 9(모름)·8(형제 없음) 처리, 음주·흡연 8 처리 → **S2 학습 때 정하고 이 표에 채움** (variables.md 1-5)

### 5-1. 기준표 판정 (`method = CHECKUP_CRITERIA`)
검진 수치는 모델 입력에 넣지 않고, 기준표로만 판정

| 필드 | 규칙 |
|---|---|
| score · model_version · factors | null |
| level | 아래 기준표 |
| checkup_record_id | 판정에 쓴 검진 기록 |
| input_snapshot | 판정에 쓴 검진 수치 + 검진 날짜 `{"checked_on": "2026-05-10", "systolic_bp": 134, "diastolic_bp": 86}` (검진 기록을 지워도 남도록) |

| 질환 | LOW (정상) | CAUTION (전단계 이상, 정답 기준과 같음) | HIGH (질환 범위) |
|---|---|---|---|
| 고혈압 | 수축기 130 미만 그리고 이완기 80 미만 | 수축기 130 이상 또는 이완기 80 이상 | 수축기 140 이상 또는 이완기 90 이상 |
| 당뇨 | 공복혈당 100 미만 그리고 당화혈색소 5.7 미만 | 공복혈당 100 이상 또는 당화혈색소 5.7 이상 | 공복혈당 126 이상 또는 당화혈색소 6.5 이상 |

- 출처: 대한고혈압학회·대한당뇨병학회 진료지침 (보고서에 지침 연도 표기)
- **쓰는 검진**: `checked_on`이 가장 최근인 검진 기록 1건
- **유효기간**: 그 검진의 `checked_on`이 예측 시점(`health_profile.created_at`) 기준 1년 이내일 때만. 지나면 기준표 행 없음 (모델 행만)
- **수치가 일부만 있을 때**
  - 있는 값 중 하나라도 기준 이상 → 그 값으로 판정 (가장 높은 단계)
  - `LOW`(정상)는 그 질환 항목이 모두 있고 모두 정상일 때만 (고혈압: 수축기·이완기 / 당뇨: 공복혈당·당화혈색소)
  - 그 외(있는 값은 정상인데 항목이 빠짐, 또는 그 질환 수치가 없음) → 기준표 행 없음 (모델 행만)
  - 이유: 일부 수치만으로 "정상"을 내면 빠진 수치가 높은 사람을 안심시킬 수 있음
- 화면 표현: "진단"이 아니라 "수치가 ○○ 범위예요" + `CAUTION`·`HIGH`는 병원 확인 권유

**대사증후군 (저장 안 함, 5-2 응답에서 매번 계산, 11/19 ERD 확정)**
- 기준 5개 중 3개 이상: 허리둘레 남 90·여 85 이상 / 중성지방 150 이상 / HDL 남 40·여 50 미만 / 혈압 130/85 이상 또는 고혈압 진단 / 공복혈당 100 이상 또는 당뇨 진단
- 약 복용은 진단 여부로 대신 (진단 없이 약 먹는 사람 데이터에 0명)
- 이상지질혈증 약은 설문에 없어 중성지방·HDL은 수치로만 판정
- 쓰는 검진·유효기간은 기준표 판정과 같음 (가장 최근 1건, 1년)
- 허리둘레는 검진 값(`checkup_records.waist_cm`)만 씀. 설문 허리둘레(`health_profiles.waist_cm`)는 기록용 (다른 4개 기준과 같은 날 잰 값이고, 직접 잰 값은 오차가 커서)
- 빠진 항목이 있으면: 해당 3개 이상 → `MET` / 빠진 항목이 모두 해당이어도 3개 미만 → `NOT_MET` / 그 외 → `UNKNOWN`
- 기준표 버전은 코드 상수로 관리
- 출처: 수정 NCEP-ATP III + 대한비만학회 허리둘레 기준

### 5-2. 최근 예측 `GET /api/v1/risk-predictions/latest` ⚕️
S-09, S-12 홈 카드
```json
{
  "health_profile_id": 31,
  "predictions": [
    { "id": 51, "disease": "DIABETES", "method": "MODEL", "score": 34, "level": "CAUTION", "created_at": "2026-11-19T10:40:00+09:00" },
    { "id": 53, "disease": "DIABETES", "method": "CHECKUP_CRITERIA", "score": null, "level": "CAUTION", "checkup_record_id": 8, "created_at": "2026-11-19T10:40:00+09:00" },
    { "id": 52, "disease": "HYPERTENSION", "method": "MODEL", "score": 21, "level": "LOW", "created_at": "2026-11-19T10:40:00+09:00" }
  ],
  "managed_diseases": [],
  "skipped_reason": null,
  "metabolic_syndrome": { "status": "UNKNOWN", "met_count": 2, "missing": ["triglyceride", "hdl_cholesterol"] }
}
```
- 질환별 가장 최근 `MODEL` 행 1개 + (있으면) `CHECKUP_CRITERIA` 행 1개
- 설문이 없으면 **404** `"아직 설문 기록이 없어요."`
- `metabolic_syndrome`: 유효한 검진이 없으면 null

### 5-3. 예측 상세 `GET /api/v1/risk-predictions/{id}` ⚕️
S-09 상세
```json
{
  "id": 51, "disease": "DIABETES", "method": "MODEL", "score": 34, "level": "CAUTION",
  "factors": [
    { "feature": "weight_kg", "direction": "UP" },
    { "feature": "father_diabetes_history", "direction": "UP" },
    { "feature": "alcohol_frequency", "direction": "DOWN" }
  ],
  "model_version": "diabetes_risk:v1",
  "changed_inputs": [ { "feature": "weight_kg", "before": 80.0, "after": 78.2 } ],
  "previous": { "id": 40, "score": 37, "level": "CAUTION", "created_at": "2026-11-12T09:10:00+09:00" },
  "created_at": "2026-11-19T10:40:00+09:00"
}
```
- `changed_inputs`: 같은 질환 직전 `MODEL` 행의 `input_snapshot`과 비교한 값. "위험도가 낮아졌어요"는 score가 실제로 내려갔을 때만, 이 값과 같이 보여줌 (REQ-NFR-003)
- `CHECKUP_CRITERIA` 행이면 `factors`·`changed_inputs`·`previous`는 null, 대신 `input_snapshot`의 판정 수치를 `{ "used_values": { "fasting_glucose": 108 }, "checked_on": "2026-05-10" }`로 내려줌
- `factors`의 feature → 화면 문구(예: `weight_kg` → "체중")는 프론트 상수 (프론트와 목록 맞춤)
- 요인 크기 숫자는 내려주지 않음 (방향만)
- 남의 것이면 404

### 5-4. 습관 시뮬레이션 `POST /api/v1/risk-predictions/simulate` ⚕️
S-10 · **저장하지 않음** (`risk_predictions`에 행 안 생김)

**요청**
```json
{ "changes": { "weight_kg": 75.0, "alcohol_frequency": 3, "alcohol_amount": 2, "smoking_current": 3 } }
```
- 바꿀 수 있는 값: `weight_kg`, `alcohol_frequency`, `alcohol_amount`, `smoking_current` (위험도를 바꾸는 생활 요인 = 체중·음주·흡연)
- 그 외 필드를 보내면 **400** `"체중·음주·흡연만 바꿔 볼 수 있어요."`
- 보낸 값만 최근 설문 값 위에 덮어서 계산. 값 범위·건너뛰기 규칙은 3-1과 같음 (예: 음주 빈도 1이면 양은 8로 서버가 채움)
- - 최근 설문에서 비해당인 문항은 바꿀 수 없음 → **400** `"지금 해당하지 않는 습관은 바꿔 볼 수 없어요."` (예: 음주 경험 "없다"인 사람이 `alcohol_frequency`를 보냄, 흡연한 적 없는 사람이 `smoking_current`를 보냄). S-10 화면은 해당하는 습관만 보여줌

**응답 200**
```json
{
  "results": [
    { "disease": "DIABETES", "before": { "score": 34, "level": "CAUTION" }, "after": { "score": 29, "level": "LOW" } },
    { "disease": "HYPERTENSION", "before": { "score": 21, "level": "LOW" }, "after": { "score": 21, "level": "LOW" } }
  ],
  "managed_diseases": [],
  "skipped_reason": null
}
```
- `before` = 최근 `MODEL` 행 점수. 없으면(예측 실패 등) 최근 설문으로 그 자리에서 계산
- 진단 "예"·임신·나이 밖은 5-0과 같이 빠짐
- 고혈압은 금연해도 점수가 거의 안 바뀜 → 화면에서 "고혈압 위험도 점수엔 변화가 거의 없어요" 안내 (흡연은 모델 입력에 들어가지만 고혈압 쪽 영향이 작음, 금연 효과가 없다는 뜻이 아님). S-10 와이어프레임과 같은 문구
- 운동은 직접 바꾸지 않고 체중 변화로 보여줌 (variables.md 2장 논의 B)
- 설문이 없으면 404

---

## 6. 건강 기록 — `health_logs`
S-19(일일 기록), S-11 뒷부분(주간 기록 6종), S-12 컨디션 · REQ-DASH-001·005

### 6-0. 종류별 값 규칙
일일 기록 값 규칙은 11/23 확정 (**정할 것 3번**). 주간 기록은 ERD 그대로.

| log_type | value | value2 | unit | 범위 | 주기 |
|---|---|---|---|---|---|
| BLOOD_PRESSURE | 수축기 | 이완기 (필수) | `mmHg` | 60~260 / 30~160 | 수시 (하루 여러 번 가능) |
| BLOOD_GLUCOSE | 혈당 | — | `mg/dL` | 40~600 | 수시 |
| ALCOHOL | 마신 잔 수 (소주잔·맥주잔으로 입력, 저장 방식은 정할 것 3번) | — | `drinks` | 0~50 | 하루 1행 권장 |
| EXERCISE | 운동 시간 | — | `minutes` | 1~600 | 수시 |
| STEPS | 걸음 수 (직접 입력) | — | `steps` | 0~100000 | 하루 1행, 다시 입력하면 덮어씀 |
| CONDITION | 좋음 2 · 보통 1 · 나쁨 0 | — | null | 0~2 | 하루 1행, 덮어씀 |
| WEIGHT | 체중 | — | `kg` | 25~300 | 수시 |
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
- 수정 허용 (**정할 것 4번**, 11/23 확정) → ERD `health_logs.updated_at` 추가

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

## 8. 챌린지·짝꿍 — 이지희 (초안 최현영)
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


## 10. 식단 — `meals`, `foods` (여현지)
S-21(식단 기록), S-22(음식 고르기), S-23(영양 결과) · REQ-FOOD-001~003, NFR-005 · **P2** (식단이 없어도 핵심 흐름은 돌아가야 함, NFR-009)

- 사진 분류는 몇 초 걸려서 **`202 + task_id` → AI 워커 → SSE** (공통 규칙). 나머지는 동기 처리
- 음식 목록은 `foods` 18행 (한 음식에 한 행, 냉면 = 물냉면, 순두부찌개 = 해물). 영양값은 식약처 OpenAPI로 미리 받아 둔 **1인분 값**
- 1차 모델은 18종 중 하나로만 답함. 목록에 없는 음식은 직접 검색(10-8)으로 고름

### 10-1. 사진 올리기 `POST /api/v1/meals` → 202 / 503
S-21 · REQ-FOOD-001

**요청** `multipart/form-data`

| 필드 | 규칙 |
|---|---|
| image | 필수. jpg / png / webp, 최대 10MB (정할 것 16번, 11/23 확정). 아이폰 HEIC는 프론트에서 jpg로 바꿔 올림. 아니면 400, 크기 초과 413 |
| eaten_at | 선택. 없으면 지금(KST). 지금보다 미래면 400 `"먹은 시간은 지금 이후로 할 수 없어요."` |

**처리 순서**
1. 이미지 저장 → `image_url` (저장 위치는 S3 답변 후 결정, ERD 정할 것)
2. `meals` 저장: `status = PENDING`, `category = MEAL`(1차는 식사만), `portion = 1.0`
3. `TaskMessage(task_type = MEAL_CLASSIFY, user_id, target_id = meals.id)`를 `ai:tasks`에 XADD
4. 큐 등록에 성공한 경우에만 **202**. 등록 실패 시 이미지와 식단 기록은 남기고 `status = FAILED`로 저장. 워커는 실행되지 않았으므로 `retry_count`는 그대로 두고 **503** 반환.

**응답 202**
```json
{ "meal_id": 101, "task_id": "8f1c2d4e-3b5a-4c6d-9e7f-0a1b2c3d4e5f", "status": "PENDING" }
```

**응답 503 — 식단·추천 공통 큐 등록 실패 (10-6·11-5)**
```json
{ "detail": "작업을 시작하지 못했어요. 잠시 후 다시 시도해 주세요." }
```
- `task_id`가 없으므로 프론트는 SSE를 기다리지 않고 C-02 실패 상태를 표시함. 10-3 목록을 새로 불러와 방금 올린 실패 기록을 선택하고, 사진을 다시 올리는 대신 같은 `meal_id`로 10-6을 호출함.

### 10-2. 분류 결과 알림 — 공통 SSE(12-6)의 `task` 이벤트
S-21, C-02 · REQ-FOOD-001, NFR-005
- 연결·인증은 12-6 그대로 (`POST /api/v1/events/ticket` → `GET /api/v1/events?ticket=...`). 식단 전용 SSE 주소는 따로 두지 않음
- 워커 처리: `status = PROCESSING` → 분류 → `candidates`·`model_version` 저장, `COMPLETED` / 3번 실패하면 `FAILED`, `retry_count + 1` → `ai:results`에 발행
- 받는 이벤트 (12-6 형식, `task_type`이 `MEAL_CLASSIFY`인 것만 식단 화면에서 씀)
```text
event: task
data: {"task_id": "8f1c2d4e-3b5a-4c6d-9e7f-0a1b2c3d4e5f", "task_type": "MEAL_CLASSIFY", "target_id": 101, "status": "COMPLETED"}
```
  - `target_id` = `meals.id`, `status`는 `COMPLETED` 또는 `FAILED`
  - 이벤트에는 후보가 없음 → 프론트가 10-4로 다시 조회해 `candidates`를 받음
- 끊긴 동안 놓친 결과는 S-21을 열 때 10-3 목록의 `status`로 확인 (`PENDING`·`PROCESSING`이 남아 있으면 분석 중 표시)

### 10-3. 하루 식단 목록 `GET /api/v1/meals?date=2026-11-19`
S-21 · REQ-FOOD-001

- 그날(KST) `eaten_at` 순. 하루 끼니 수가 적어서 커서 없이 전부 줌
- `daily_total`: 그날 **음식을 고른 식단** 전체의 `nutrients` 합 (하루 요약용. 끼니별 피드백은 10-9의 이 끼니까지 누적 `running_total`)

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
- 후보마다 `foods`의 1인분 값을 붙여 응답함 (`serving_size`, `serving_unit`, `kcal`). DB의 `candidates`에는 `food_id`·`score`만 저장하고 응답할 때 붙임 → S-22에서 고르기 전에도 "1인분 797mL · 390kcal"을 보여 주고, 저장 기본값은 `portion` 1.0
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

### 10-6. 다시 분류 `POST /api/v1/meals/{id}/retry` → 202 / 503
C-02 · REQ-FOOD-001, NFR-005
- `FAILED`일 때만. 아니면 409 `"다시 분석할 수 없는 상태예요."`
- `status = PENDING`으로 바꾸고 같은 `meals.id`로 새 `TaskMessage` 등록. 성공하면 **202** `{ "meal_id", "task_id", "status": "PENDING" }`.
- 큐 등록에 실패하면 같은 행을 `FAILED`로 되돌리고 `retry_count`는 그대로 유지. **503** 응답은 10-1과 같으며, SSE를 기다리지 않음.
- `retry_count`가 **3 이상**이면 429 `"분석은 3번까지 할 수 있어요. 직접 골라 주세요."` → 10-5로 직접 고르기 (정할 것 18번)
  - 처음 분석 + 다시 분석 2번 = 분석 3번. 워커 안에서도 매번 3번씩 재시도하므로 충분함
  - `retry_count`는 식단 한 건의 누적 실패 횟수(워커가 최종 `FAILED`로 끝낼 때 +1)라 하루 단위가 아님, 컬럼 추가 없음

### 10-7. 삭제 `DELETE /api/v1/meals/{id}` → 204
- 분석 중에도 삭제 가능. 워커는 `meals` 행이 없으면 건너뛰고 XACK (워커 5단계 DB 연결에서 반영)
- 저장한 이미지도 함께 지움

### 10-8. 음식 목록·검색 `GET /api/v1/foods?q=국수`
S-22 "목록에 없어요" · REQ-FOOD-001·002
- `q` 없으면 18행 전부, 있으면 `name`·`model_label` 부분 일치. 18행이라 커서 없이 전부 줌
- 영양값은 **1인분 기준**, `serving_unit`은 `G` / `ML` (18행 중 10행이 mL)

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
S-23 · REQ-FOOD-003 · 11/20 확정 (정할 것 17번)

**하루 기준치** — 2,000kcal 기준, 모든 사용자 같은 값
| key | 하루 기준치 | 근거 |
|---|---|---|
| `sodium_mg` | 2,000 | 식약처 1일 영양성분 기준치. 고혈압(대한고혈압학회 2026: 나트륨 2,000mg 이하)·당뇨(대한당뇨병학회 2025: 2,300mg 이내) 모두 만족 |
| `sugar_g` | 100 | 식약처 기준치(총당류) = 2025 한국인 영양소 섭취기준 총당류 에너지 20% 이내. `sugar_g`는 첨가당이 아니라 총당류 |
| `carbs_g` | 324 | 식약처 기준치 = 2025 섭취기준 탄수화물 권장 범위(에너지 50~65%)의 상한 65% |

- 질환별로 기준값을 다르게 두지 않음 → "당뇨면 더 먹어도 되나?"처럼 읽히는 것을 막고 계산을 단순하게 함
- 필요 열량(성별·나이·키·몸무게) 개인화는 12/4 이후 개선

**강조 항목(`focus`)** — 최근 설문의 진단 여부만 씀
- `is_hypertension_diagnosed = true` → `sodium_mg`, `is_diabetes_diagnosed = true` → `sugar_g`·`carbs_g`, 둘 다면 셋 다, 진단 없으면 빈 배열
- 예측 위험도·검진 수치가 질환 범위여도 강조하지 않음 (예측을 진단처럼 쓰지 않음, NFR-001). 대신 일반 기준으로 보여 주고 병원 확인 권유는 예측·검진 화면(S-09)에서
- `is_pregnant = true`면 `focus` 빈 배열 + `notice` 문구 "임신 중에는 의료진 안내를 따르세요."
- 1차는 위 규칙대로. 미진단·경계 사용자(예: 페르소나 김지은)는 강조가 안 뜨는 문제 → 약한 참고 표시·관심 항목 고르기를 2차에 검토 (정할 것 29번)

**`level`** — 지침 값이 아닌 서비스 설계값 (부족은 안내하지 않음)
| level | 조건 |
|---|---|
| `DAILY_OVER` | 이 끼니까지 누적(`running_total`)이 하루 기준치의 100% **초과** |
| `MEAL_HIGH` | 이 끼니 값이 하루 기준치의 1/3(33.3%) 이상 |
| `OK` | 그 외 |

- 둘 다 해당하면 `DAILY_OVER`. 값이 null(예: 닭개장 탄수화물)이면 그 항목은 `level`·`percent` 모두 null
- **누적 = 이 끼니까지** (11/19 리뷰 (가)안): 같은 날(KST) 음식을 고른 식단 중 `eaten_at`이 이 끼니 이하인 것만 더함 (같은 시각이면 `id` 순). 저녁을 기록해도 아침 결과는 바뀌지 않음 → 끼니별 결과가 언제 열어도 같음
  - 나중에 더 이른 시각의 끼니를 추가로 기록하면 그 뒤 끼니들의 누적은 함께 바뀜 (먹은 순서 기준이라 맞는 동작)
  - 그날 전체 합계는 10-3 `daily_total` (하루 요약용, `level` 없음)
- **기록한 끼니만** 더한 값 → 화면에 "기록한 끼니 기준" 표시 (한 끼만 기록하면 `DAILY_OVER`는 거의 안 뜸)
- 화면 문구는 담담하게 "하루 기준치의 ○%예요" (NFR-007 말투). "많아요"·"위험해요" 같은 표현은 쓰지 않음

```json
"feedback": {
  "basis": "2,000kcal 기준 · 기록한 끼니 기준",
  "focus": ["sodium_mg"],
  "notice": null,
  "items": [
    { "key": "sodium_mg", "meal_value": 1326.6, "meal_percent": 66.3, "running_total": 2211.0, "daily_reference": 2000, "percent": 110.5, "level": "DAILY_OVER" },
    { "key": "sugar_g", "meal_value": 5.0, "meal_percent": 5.0, "running_total": 8.3, "daily_reference": 100, "percent": 8.3, "level": "OK" },
    { "key": "carbs_g", "meal_value": 9.9, "meal_percent": 3.1, "running_total": 16.5, "daily_reference": 324, "percent": 5.1, "level": "OK" }
  ]
}
```
- 예시: 아침 육개장 1인분(나트륨 884.4) 다음 저녁 육개장 1.5인분(1326.6)을 연 경우. 아침 식단을 열면 누적 884.4 → 44.2%, `MEAL_HIGH`
- `meal_percent` = 이 끼니 값 ÷ 하루 기준치 × 100, `percent` = `running_total` ÷ 하루 기준치 × 100 (소수 첫째 자리)
- 화면 하단 의료 안내 문구(C-01) 고정
- "다음 끼니에 바꿀 한 가지"(S-23 아래쪽)는 11장 LLM 추천(REQ-LLM-002, 김민준)


## 11. LLM 추천 — `recommendations`, `llm_usage_logs` (김민준)
S-12(홈), S-23(영양 결과), C-02(처리 중·실패) · REQ-LLM-001·002, NFR-001·002·005·006·011·012·017

- 이번 명세는 `DAILY_ACTION`과 `MEAL_ALTERNATIVE`만 다룸. 날씨 대체 활동(LLM-003)·위험 요인 설명(LLM-004)·주간 리포트(LLM-005)는 검토 중이라 경로를 확정하지 않음. 식단 사진 분류·비전 보조는 10장 범위.
- 모든 요청은 로그인 필요(1장). 사용자와 날짜는 서버에서 결정하고, 추천에 쓸 기록은 로그인 사용자의 저장된 데이터에서 읽음. 생성 요청 본문 없음.
- 화면은 **저장본을 먼저 조회**하고, 저장본이 없거나 사용자가 실패 후 다시 시도할 때만 생성 요청. 새 작업만 **202 + `task_id`**, 이미 처리 중이거나 완료된 건 다시 큐에 넣지 않음.

### 11-1. 오늘의 한 가지 생성 `POST /api/v1/recommendations/daily` → 202 / 200 ⚕️
S-12 · REQ-LLM-001

- `rec_type = DAILY_ACTION`, `target_on`은 요청 시점의 KST 날짜. **사용자·유형·날짜당 1행**을 쓰고 실패 시 같은 행을 재사용함.
- 최근 건강·생활 기록에서 확인할 수 있는 정보만 쓰고, 사용자가 현실적으로 해볼 수 있는 예방 행동 **1개**를 제안함. 입력에 없는 습관이나 제약을 추정하지 않음.
- 요청이 겹쳐도 중복 생성되지 않도록, ERD의 `(user_id, rec_type, target_on)` 인덱스는 조회용으로 두고 같은 사용자에 대한 추천 확인·생성·재시도 상태 변경을 DB 트랜잭션으로 직렬화함 (예: 사용자 행 잠금).

### 11-2. 오늘의 한 가지 조회 `GET /api/v1/recommendations/daily` → 200 ⚕️
- 기본은 오늘(KST)의 저장본. 선택 쿼리 `target_on=YYYY-MM-DD`로 기준 날짜를 지정할 수 있음(자정을 넘겨 처리된 작업 등). 날짜 형식이 잘못되면 **422**.
- 해당 날짜에 저장된 추천 행이 없으면 **404** `"저장된 오늘의 추천이 없어요."` → 홈은 오늘 날짜의 첫 조회가 404일 때만 11-1 호출. 조회는 LLM을 호출하거나 큐를 만들지 않음.

### 11-3. 다음 끼니에 바꿀 한 가지 생성 `POST /api/v1/meals/{id}/recommendation` → 202 / 200 ⚕️
S-23 · REQ-LLM-002

- 경로의 `id`는 **`meals.id`**. 식단이 없거나 다른 사용자의 기록이면 **404**. 10-5에서 음식을 골라 저장하기 전(`food_id = null`)이면 **409** `"음식을 골라 저장한 뒤 추천을 받아 주세요."` → 사진 분류에 실패했더라도 음식을 직접 골라 저장했으면 생성 가능.
- `rec_type = MEAL_ALTERNATIVE`, `meal_id = meals.id`, `target_on`은 기준 식단의 `eaten_at`을 KST로 변환한 날짜. `meal_id` 유니크 기준으로 **식단당 1행**을 쓰고 실패 시 같은 행을 재사용함.
- 확정된 메뉴·먹은 양과 사용자의 기록을 바탕으로 다음 끼니에 적용할 대체 메뉴나 바꿀 점 **1개**를 제안함. 영양값은 10장의 저장값을 쓰고, 값이 없는 항목은 추정하지 않음.

### 11-4. 다음 끼니 추천 조회 `GET /api/v1/meals/{id}/recommendation` → 200 ⚕️
- 해당 식단의 저장본을 반환. 식단이 없거나 다른 사용자의 것이면 **404** `"식단 기록을 찾을 수 없어요."` → 생성하지 않음.
- 내 식단에 추천 행만 없으면 **404** `"저장된 식단 추천이 없어요."` → 음식 저장이 끝난 S-23에서만 11-3 호출. 식단 추천이 없어도 영양 결과(10-4·10-9)는 그대로 표시.

### 11-5. 생성·조회 공통 응답 및 재시도

| 호출·현재 상태 | 처리 | 응답 |
|---|---|---|
| POST · 추천 없음 | `PENDING` 행을 저장하고 새 작업 등록 | **202** |
| POST · `PENDING` / `PROCESSING` / `COMPLETED` | 새 작업 없이 기존 저장본 반환 | **200**, 조회와 같은 본문 |
| POST · `FAILED`이고 `retry_count < 3` | 같은 추천 ID로 `PENDING` 전환, 새 `task_id` 발급 | **202** |
| POST · `FAILED`이고 `retry_count >= 3` | 상태를 바꾸거나 새 작업을 등록하지 않음 | **429** |
| GET · 행 존재 | 상태와 저장본 반환. 재시도는 시작하지 않음 | **200** |
| POST · 큐 등록 실패 | 행은 `FAILED`로 저장. 워커가 실행되지 않았으므로 `retry_count`는 그대로 둠 | **503**, 10-1과 동일한 `{ "detail": "작업을 시작하지 못했어요. 잠시 후 다시 시도해 주세요." }`. `task_id` 없음, SSE 대기 안 함 |

**응답 202** — `recommendation_id`는 `recommendations.id`이고 `task_id`와 다름.
```json
{ "recommendation_id": 207, "task_id": "712d9c48-4fd2-4da0-8aed-53044372477e", "status": "PENDING" }
```

**응답 200** — 저장 추천 공통 형식. 아래 출처와 URL은 형식을 보여 주기 위한 예시.
```json
{
  "id": 207,
  "rec_type": "DAILY_ACTION",
  "target_on": "2026-11-20",
  "meal_id": null,
  "status": "COMPLETED",
  "content": "점심을 먹고 가능한 날에 가볍게 걸어보는 건 어때요? [1]",
  "sources": [
    { "number": 1, "title": "신체활동 가이드(예시)", "url": "https://example.com/activity-guide" }
  ],
  "retry_count": 0,
  "created_at": "2026-11-20T11:00:01+09:00",
  "updated_at": "2026-11-20T11:00:08+09:00"
}
```
- 식단 추천은 `rec_type = MEAL_ALTERNATIVE`, `meal_id`에 기준 식단 ID를 반환. `PENDING`·`PROCESSING`·`FAILED`에서는 `content`·`sources`가 모두 `null`.
- `retry_count`는 10-6과 같이 추천 한 건의 누적 작업 실패 횟수. 최초 값은 0이며 워커가 한 작업을 최종 `FAILED`로 저장할 때 1 증가함. **최초 생성 1번 + 재생성 2번**까지로, `retry_count >= 3`이면 **429** `"추천을 다시 요청할 수 있는 횟수를 모두 사용했어요."`.
- 워커 내부 실행은 한 작업당 최대 3번(최초 1번 포함). 내부 재시도마다 `retry_count`를 올리지 않음.
- 근거가 부족하면 `COMPLETED`로 저장하되 추천을 지어내지 않고 `content = "지금은 근거가 충분하지 않아 추천하기 어려워요."`, `sources = []`를 반환함. 기술적인 생성 실패(`FAILED`)와 구분함.

### 11-6. 워커와 완료 알림 — 공통 SSE(12-6)
1. 서버가 추천 행을 저장하고 `TaskMessage(task_type = RECOMMEND_LLM, user_id, target_id = recommendations.id)`를 `ai:tasks`에 등록. 메시지에 건강 수치·프롬프트 본문을 넣지 않음.
2. 워커가 대상 행을 읽어 `PROCESSING`으로 전환. 공인 가이드 검색 결과 상위 3~5개 안에서만 근거를 쓰고, 결과 본문의 `[번호]`는 서버에서 확인한 실제 출처 배열과 일치시킴. 식별정보는 LLM 입력에서 제외함.
3. 완료 시 `content`·`sources`·`model`·`prompt_version`과 `COMPLETED`를 먼저 저장. 최종 오류는 `FAILED` 저장. LLM 호출별 사용량·성공 여부는 `llm_usage_logs`에 기록하고 프롬프트·응답 본문은 사용량 로그에 남기지 않음.
4. 상태 저장 후 `ai:results`에 발행. 12-6의 `task` 이벤트에서 받은 `target_id`는 **추천 ID**이며 식단 ID가 아님.
```text
event: task
data: {"task_id": "712d9c48-4fd2-4da0-8aed-53044372477e", "task_type": "RECOMMEND_LLM", "target_id": 207, "status": "COMPLETED"}
```
- 이벤트는 `COMPLETED` / `FAILED`만 알림. 프론트는 요청한 화면의 11-2 또는 11-4로 갱신함. SSE를 놓친 경우에도 같은 GET으로 저장 상태를 확인함.
- 결과 일관성(REQ-NFR-017)을 위해 모델별 `temperature` 등 생성 설정을 고정하고, 설정 변경 시 `prompt_version`을 올려 어떤 설정으로 생성했는지 추적함.
- 추천은 진단·처방 또는 위험도 재계산 결과가 아님. 화면에는 C-01 의료 안내를 표시함.

## 12. 알림 — `notifications`, `notification_settings`, `push_subscriptions`, `custom_reminders` (김지연)
S-24~S-26, C-03 · REQ-NOTI-001~007, 009

**공통 원칙**
- 경로 두 가지: 사이트를 열어 둔 동안은 **SSE**(12-6), 닫혀 있으면 **웹 푸시**(12-5). 둘 다 `notifications`에 1행 남김
- 알림 제목·본문·리마인더 이름은 **서버 로그에 남기지 않음**, 짝꿍 알림엔 수치를 넣지 않음 (REQ-PAIR-003, NFR-006)
- 방해 금지 시간(`users.quiet_start`~`quiet_end`)에는 **웹 푸시를 보내지 않고** `notifications` 행만 쌓음 (앱을 열면 목록에서 보임)
- 보관 30일 (ERD Note), 지난 행은 매일 정리

### 12-0. 알림 종류 (`notification_type`)
| 종류 | 언제 | 설정 | 누르면 |
|---|---|---|---|
| `CHALLENGE_REMINDER` | 정한 시각에 오늘 아직 안 한 챌린지가 있으면. 다 했으면 안 보냄 (NOTI-004) | 요일·시각 (모든 챌린지 공통 1개) | S-12 홈 |
| `PARTNER_ACTIVITY` | 짝꿍이 체크했을 때, 응원 받았을 때, 짝꿍·챌린지 초대가 왔거나 수락됐을 때 (NOTI-005) | 켜기·끄기만 | S-17 / S-16 |
| `STREAK_ACHIEVED` | 이번 주 목표를 채웠을 때, 연속 주 기록이 끊기기 전(일요일 저녁) (NOTI-006). `CHALLENGE_REMINDER`를 끄면 같이 꺼짐 | 켜기·끄기만 | S-15 |
| `WEEKLY_REPORT` | 주 1회 리포트가 만들어지면 (NOTI-007) | 요일·시각 | S-20 |
| `CUSTOM_REMINDER` | 사용자가 만든 리마인더 시각 (NOTI-009) | 리마인더마다 (12-4), 설정 행은 전체 켜기·끄기 | S-26 |

### 12-1. 알림 목록 `GET /api/v1/notifications?limit=20&cursor=` · 읽음
S-24 · REQ-NOTI-002
```json
{ "items": [ { "id": 77, "noti_type": "PARTNER_ACTIVITY", "title": "현영님이 오늘 걷기를 완료했어요", "body": null, "link": "/challenges/30", "is_read": false, "created_at": "2026-11-19T12:40:00+09:00" } ],
  "next_cursor": 70, "unread_count": 3 }
```
- 최신순, 공통 목록 형식. `unread_count`는 상단 벨 배지용
- `GET /api/v1/notifications/unread-count` → `{ "unread_count": 3 }` (홈 진입 시 가볍게)
- `POST /api/v1/notifications/{id}/read` → 204 (`is_read = true`, `read_at = 지금`, 이미 읽었으면 그대로 204)
- `POST /api/v1/notifications/read-all` → 204
- 남의 알림 id는 404

### 12-2. 알림 설정 `GET /api/v1/notification-settings` · `PUT /api/v1/notification-settings`
S-25 · REQ-NOTI-001
**GET 응답 200** (행이 없는 종류는 기본값으로 채워서 줌 → 5종 항상 다 옴)
```json
{
  "settings": [
    { "noti_type": "CHALLENGE_REMINDER", "is_enabled": true, "days": ["MON", "TUE", "WED", "THU", "FRI"], "notify_at": "19:00" },
    { "noti_type": "PARTNER_ACTIVITY", "is_enabled": true, "days": null, "notify_at": null },
    { "noti_type": "STREAK_ACHIEVED", "is_enabled": true, "days": null, "notify_at": null },
    { "noti_type": "WEEKLY_REPORT", "is_enabled": true, "days": ["SUN"], "notify_at": "20:00" },
    { "noti_type": "CUSTOM_REMINDER", "is_enabled": true, "days": null, "notify_at": null }
  ],
  "quiet_start": "22:00",
  "quiet_end": "07:00"
}
```
**PUT** — 보낸 종류만 바꿈(없으면 그 행 생성), `quiet_start`·`quiet_end`도 같이 받음
| 필드 | 규칙 |
|---|---|
| days | 요일 배열(`MON`~`SUN`), 빈 배열·null이면 매일. DB엔 쉼표 문자열로 저장 (ERD) |
| notify_at | `HH:MM` (10분 단위). 스케줄형(`CHALLENGE_REMINDER`·`WEEKLY_REPORT`)만, 이벤트형에 보내면 400 |
| quiet_start · quiet_end | 둘 다 있거나 둘 다 null. 시작이 끝보다 늦으면 다음 날까지 (예: 22:00~07:00) |
- 기본값(처음 행이 없을 때): 주간 리포트 일요일 20:00, 나머지 켜짐, 방해 금지 없음 (정할 것 27번, 11/23 확정). 챌린지 리마인더 요일·시각은 챌린지를 설정할 때 정함 → 아래 `CHALLENGE_REMINDER`의 `days`·`notify_at` 정리는 후속 PR
- `notify_at`이 방해 금지 시간 안이면 저장은 하고 응답에 `"warnings": ["방해 금지 시간이라 이 시각엔 푸시가 가지 않아요."]`

### 12-3. 스케줄 발송 (API 아님)
- 스케줄러가 **10분마다** 이번 10분 안에 보낼 `CHALLENGE_REMINDER`·`WEEKLY_REPORT`·`CUSTOM_REMINDER`를 찾아 `notifications` 생성 → SSE·웹 푸시
- 실행 위치(FastAPI 안 / AI 워커 / 별도 프로세스)는 구현 때 결정 → 정할 것 28번
- 같은 알림이 두 번 가지 않게 (사용자, 종류, 대상, 날짜·시각)로 중복 확인

### 12-4. 직접 만든 리마인더 `/api/v1/custom-reminders`
S-26 · REQ-NOTI-009
| API | 내용 |
|---|---|
| `GET /api/v1/custom-reminders` | 내 리마인더 전부 (최대 10개라 커서 없음) |
| `POST /api/v1/custom-reminders` → 201 | `{ "title": "혈압 재기", "days": ["MON", "WED", "FRI"], "remind_at": "08:00" }` |
| `PATCH /api/v1/custom-reminders/{id}` | `title`·`days`·`remind_at`·`is_enabled` 중 보낸 것만 |
| `DELETE /api/v1/custom-reminders/{id}` → 204 | 실제 삭제 (ERD) |
- `title` 1~100자. **약 이름·용량을 적도록 유도하지 않음**(화면 예시는 "영양제 먹기·혈압 재기·물 마시기"), 짝꿍에게 안 보임, 로그 금지
- 1인당 10개 → 넘으면 409 `"리마인더는 10개까지 만들 수 있어요."`
- `remind_at`은 `HH:MM`(10분 단위, 12-3 주기와 맞춤). 방해 금지 시간과 겹치면 저장하고 `warnings`로 안내 (ERD Note)

### 12-5. 웹 푸시 구독 `POST /api/v1/push-subscriptions` · `DELETE`
S-25 "웹 푸시 켜기", C-03 · REQ-NOTI-003
- `GET /api/v1/push-subscriptions/vapid-public-key` → `{ "public_key": "..." }` (서비스 워커 구독할 때 씀, **비밀키는 `.env`에만**)
- `POST` → 201 / 200 (브라우저 `PushSubscription.toJSON()` 그대로)
```json
{ "endpoint": "https://fcm.googleapis.com/fcm/send/...", "keys": { "p256dh": "BN...", "auth": "k8..." } }
```
  - 같은 `endpoint`가 이미 있으면 `user_id`·키를 갱신하고 200 (ERD upsert), 새로 만들면 201. `user_agent`는 요청 헤더에서 서버가 채움
- `DELETE /api/v1/push-subscriptions` `{ "endpoint": "..." }` → 204 (이 기기 푸시 끄기, 로그아웃 2-4에서도 호출)
- 발송할 때 푸시 서비스가 404·410을 주면 그 행 바로 삭제, 성공하면 `last_used_at` 갱신
- 권한 요청은 버튼을 눌렀을 때만, 아이폰은 iOS 16.4+ 홈 화면 추가 후에만 → 프론트가 C-03 안내 (API 없음)

### 12-6. SSE 연결 `GET /api/v1/events` (공통, 정할 것 20번 확정)
알림(12장)·식단 분류(10-2)·LLM 추천(11장)·결과지 인식(4-6) 결과를 **연결 하나**로 받음
- 브라우저 `EventSource`는 `Authorization` 헤더를 못 붙임 → **SSE 티켓** 방식
  1. `POST /api/v1/events/ticket` (로그인 필요) → `{ "ticket": "...", "expires_in": 30 }` (Redis 30초, 1회용)
  2. `GET /api/v1/events?ticket=...` → `text/event-stream`. 티켓이 없거나 만료면 401
  - access 토큰을 URL에 넣지 않으려고(서버·프록시 로그에 남음) 티켓을 따로 둠
- 이벤트 형식 (`event:` 이름 + `data:` JSON)
```text
event: notification
data: {"id": 77, "noti_type": "PARTNER_ACTIVITY", "title": "현영님이 오늘 걷기를 완료했어요", "link": "/challenges/30"}

event: task
data: {"task_id": "8f1c...", "task_type": "MEAL_CLASSIFY", "target_id": 101, "status": "COMPLETED"}
```
  - `task` 이벤트는 AI 워커가 `ai:results`에 발행한 값 중 위 4개만 내려줌 (`user_id`로 받을 사람을 찾고 응답엔 안 넣음). 결과 내용은 프론트가 해당 조회 API(10-4 등)로 다시 가져옴
- 30초마다 `: ping` 주석으로 연결 유지, 끊기면 브라우저가 다시 연결 → **새 티켓**을 받아 다시 연결 (끊긴 동안 놓친 알림은 12-1 목록으로 확인)
- 한 사람이 탭·기기 여러 개로 연결해도 모두에게 보냄


---

## 9. 정할 것
| # | 내용 | 제안 | 누구랑 |
|---|---|---|---|
| 1 | 마이(S-27)에서 키·가족력 등 "안 묻는 문항" 수정 방법 | 새 kind `EDIT` 추가 없이, WEEKLY 전체 모드(모든 문항 받음)로 새 행 저장. 또는 enum에 `EDIT` 추가 | ERD(김지연·이지희) |
| 2 | 검진 기록 삭제 시 예측 행 처리 | ✅ 11/19 ERD 확정(#37): `risk_predictions.checkup_record_id` FK `ON DELETE SET NULL`, 당시 값은 `input_snapshot`에 남음 | — |
| 3 | 일일 기록 값 규칙(6-0 위쪽 7종) | ✅ 11/23 확정: 혈압 60~260, 혈당 40~600, 음주 소주잔·맥주잔, 운동 분 단위, 걸음 수 ~10만 보(하루 1행 덮어씀), 컨디션 6-0 그대로, 체중 ~300kg. 음주 소주잔·맥주잔 저장 방식(따로 받을지·환산할지)은 미정 | ERD·프론트 |
| 4 | 건강 기록 수정 허용 여부 | ✅ 11/23 확정: 허용, `health_logs.updated_at` 추가 (6-3) | — |
| 5 | 주간 재설문 하루·주 몇 번까지 | ✅ 11/19 확정: 같은 주에 여러 번 해도 새 행(이력 보존), 추이는 주의 마지막 값만 사용 (7-1) | — |
| 6 | 예측 실패 시 설문 저장 여부 | ✅ 11/19 확정: 설문은 저장, `prediction_error: true` 후 재시도 버튼 (3-1) | — |
| 7 | 설문 문항 정의 API(3-6) 할지 | ✅ 11/23 확정 (S-11 fetch 교체는 S-11 담당, S-06 뒤 결정): 서버 상수 하나가 기준, 3-6이 그대로 내려줌. 프론트는 같은 모양 상수로 시작해 S-11 전에 fetch로 교체. NUMBER·BOOLEAN 타입, `only_for`·`text_by_gender`, WEEKLY `ask_when_applicable`, 버전 다르면 409 | 문항 내용 장성은 / 3-1 구현 담당 / 프론트 |
| 8 | 대시보드 챌린지 달성률 계산식 | 8-13: Σ min(체크, 개인 목표) ÷ Σ 개인 목표 | 이지희(8장)·최현영(7장) |
| 9 | 검진 수치가 있을 때 판정 | ✅ 11/19 확정: 모델 점수 행 항상 + 기준표 행 추가, 추이는 모델 점수. 가장 최근 검진 1건·1년 이내만, 정상은 그 질환 항목이 모두 있을 때만 (5-1) | — |
| 10 | 서비스 방향(보건소·보험사 기관 화면)이 채택되면 계정 역할·권한 | 보험사 역할은 API에서 달성 여부만 내려주도록 막음 (화면이 아니라 서버에서) | 전원 |
| 11 | `challenge_templates.category` 값 | ✅ 11/19 확정: 대문자 7종 (ERD PR에서 반영) | — |
| 12 | 짝꿍 끊기·호스트 나가기 | ✅ 11/19 확정 → 8-6·8-8. 호스트 넘기기는 1:N만, 1:1은 남은 사람이 고르기. `created_by` = 현재 호스트 (컬럼 추가 없음) | — |
| 13 | "연속" 기준 | ✅ 11/19 확정: 목표 채운 주 연속 (8-9) | — |
| 14 | 체중 챌린지 체크와 체중 기록 연결 | 체중 기록(`health_logs` WEIGHT)을 남기면 그날 체중 챌린지 자동 체크 (수치는 짝꿍에게 안 감) — 선택 | 백엔드 |
| 15 | 초대 링크 만료 | ✅ 11/19 확정: created_at 기준 7일 (8-2~8-4) | — |
| 16 | 식단 사진 형식·크기 | ✅ 11/23 확정: jpg / png / webp, 최대 10MB. 아이폰 HEIC는 프론트에서 jpg로 바꿔 올림 (10-1) | — |
| 17 | 식단 피드백 하루 기준량·판단 기준 (10-9) | ✅ 11/20 확정: 식약처 1일 기준치(나트륨 2,000mg·당류 100g·탄수화물 324g, 2,000kcal), 질환별 값 차이 없음, 강조는 설문 진단 "예"만, `level` = 끼니 1/3 이상·이 끼니까지 누적 100% 초과, 부족 안내 없음 | 전원(식단 여현지) |
| 18 | 식단 재분류 횟수 제한 (10-6) | ✅ 11/19 확정: `retry_count` 3 이상이면 429 (누적 기준, 컬럼 추가 없음). 처음 분석 포함 3번 = 다시 분석은 2번, 문구 "분석은 3번까지" | — |
| 19 | 목록에 없는 음식 (10-8) | 1차는 `foods` 18행 안에서만 검색. 식약처 API 실시간 검색은 호출 한도·캐시 문제로 S5 이후 검토 | 여현지·백엔드 |
| 20 | 공통 SSE 명세 | ✅ 11/19 확정(#41): 연결 하나(`GET /api/v1/events`), 티켓 인증(30초 1회용), 이벤트 `notification` / `task` (12-6). 10-2 식단 분류 결과도 이 연결로 받음 | — |
| 21 | 식단 비전 LLM 보조 (REQ-FOOD-001) | 쓸지 여부, top-1 확률 기준, 18종 밖 음식 처리. 쓰면 10-2 워커 처리 안에서 호출(새 API 없음) | 여현지·LLM(김민준) |
| 22 | 필수 동의·철회 (2-1·2-6) | 이용약관·개인정보·민감정보 3종 모두 필수, 하나라도 철회하려면 탈퇴로 진행 (건강정보 없이 쓸 수 있는 기능이 없어서) | 전원 |
| 23 | 로그아웃 후 access 토큰 (2-4) | ✅ 11/23 확정: 블랙리스트 없이 access 만료 30분, 로그아웃하면 refresh 쿠키만 삭제 | — |
| 24 | 성별·생년월일 수정 (2-5) | ✅ 11/20 확정: 사용자는 직접 수정 불가(예측 입력이라 이력 기준이 바뀜). 고치려면 관리자에게 요청 → 관리자가 수정 | — |
| 25 | 비밀번호 찾기 방식 (2-7) | ✅ 11/19 확정: 이메일 인증번호(6자리, 10분, 5번 틀리면 폐기). 아이폰 PWA에서 링크는 사파리로 열려 흐름이 끊겨서. REQ-USER-004·Figma M15·M16과 맞춤 | — |
| 26 | 탈퇴 시 삭제 범위·보관 (2-8) | 건강 정보 즉시 삭제, `users`는 비활성 + 이메일·닉네임 지움, 체크·응원은 "탈퇴한 사용자"로 남김 → 개인정보 처리방침과 맞춤 | 전원 |
| 27 | 알림 기본값 (12-2) | ✅ 11/23 확정: 주간 리포트 일요일 20:00, 나머지 켜짐, 방해 금지 없음. 챌린지 리마인더는 기본 시각 없이 챌린지 설정할 때 정함 | — |
| 28 | 스케줄 발송 위치 (12-3) | 10분 주기. FastAPI 안 / AI 워커 / 별도 프로세스 중 구현 때 결정 | 백엔드 |
| 29 | 미진단·경계 사용자의 식단 피드백 강조 (10-9) | 1차는 진단 "예"만 강조. 2차 후보: (가) 최근 예측이 주의·높음이면 `focus`와 별도로 약한 표시(예: `watch` 필드, 문구 "참고로 보면 좋은 항목", 강조 색 없음 + C-01) (나) 사용자가 마이에서 관심 항목(나트륨·당류·탄수화물)을 직접 고름. (가)는 예측을 진단처럼 쓰지 않는지(NFR-001) 함께 확인 | 식단(여현지)·예측(장성은)·프론트(김지연) |
