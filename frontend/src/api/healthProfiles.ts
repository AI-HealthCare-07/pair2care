// frontend/src/api/healthProfiles.ts
// api.md 3장: 3-1 설문 저장(POST /health-profiles), 3-6 문항 정의(GET /health-profiles/questions)
// apiFetch는 4xx/5xx에서 throw하지 않으므로 공통 ApiError(status, message, code, field)로 바꿔 던짐 (client.ts의 toApiError).

import { apiFetch, toApiError, type ApiError } from './client'
import type { HealthProfileRequest, SurveyDefinition, SurveyKind } from '../survey/types'

// ─────────────────────────────────────────────
// 응답 타입 (3-1 응답 201)
// ─────────────────────────────────────────────

export type Disease = 'DIABETES' | 'HYPERTENSION'

export interface Prediction {
  id: number
  disease: Disease
  method: 'MODEL' | 'CHECKUP_CRITERIA' // CHECKUP_CRITERIA는 score가 null
  score: number | null
  level: 'LOW' | 'CAUTION' | 'HIGH'
}

export interface HealthProfile {
  id: number
  kind: SurveyKind
  survey_version: string
  created_at: string
  [field: string]: number | boolean | string | null // 요청 필드 전부 + 서버가 채운 코드(8·888)
}

export interface CreateHealthProfileResponse {
  health_profile: HealthProfile
  predictions: Prediction[]
  managed_diseases: Disease[] // 진단 "예"라서 예측 안 한 질환 (api.md 예시는 빈 배열 → 질환 이름 배열로 가정)
  skipped_reason: 'PREGNANT' | 'AGE_OUT_OF_RANGE' | null
  prediction_error: boolean // true면 설문은 저장됐고 예측만 실패
}

// ─────────────────────────────────────────────
// 에러 (api.md 1장 에러 code 목록, 3-1 에러 목록)
// ─────────────────────────────────────────────

/** 화면이 해야 할 일 (api.md 3-1 에러 목록의 "프론트 처리") */
export type SurveyErrorAction =
  | 'RELOAD_DEFINITION' // 409 SURVEY_VERSION_MISMATCH: 3-6을 다시 받아 화면을 새로 그림 (같은 field의 입력값은 유지)
  | 'GO_ONBOARDING' // 409 ONBOARDING_REQUIRED: S-06으로
  | 'GO_HOME' // 409 ONBOARDING_ALREADY_DONE: 홈으로
  | 'FOCUS_FIELD' // 400 SURVEY_FIELD_INVALID: detail을 띄우고 field 문항으로 이동 (field가 정의에 없으면 detail만 위에)
  | 'RECHECK_INPUT' // 422: "입력값을 확인해 주세요"
  | 'SHOW_MESSAGE' // 그 외: detail만 보여 줌. 401(세션 만료)은 가드가 보던 화면(from)을 담아 /login으로 보냄 (#134)

export function surveyErrorAction(err: ApiError): SurveyErrorAction {
  if (err.status === 422) return 'RECHECK_INPUT'
  if (err.status === 409) {
    if (err.code === 'SURVEY_VERSION_MISMATCH') return 'RELOAD_DEFINITION'
    if (err.code === 'ONBOARDING_REQUIRED') return 'GO_ONBOARDING'
    if (err.code === 'ONBOARDING_ALREADY_DONE') return 'GO_HOME'
  }
  if (err.status === 400 && err.code === 'SURVEY_FIELD_INVALID') return 'FOCUS_FIELD'
  return 'SHOW_MESSAGE'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, options)
  // 422(detail이 배열)는 toApiError가 기본 문구로 바꿈. 설문 화면은 422를 자기 문구("입력값을 확인해 주세요")로 처리
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as T
}

// ─────────────────────────────────────────────
// API
// ─────────────────────────────────────────────

/** 3-6 문항 정의. WEEKLY는 사용자마다 달라서(ask_when_applicable) 캐시하지 않음 */
export function getSurveyDefinition(kind: SurveyKind): Promise<SurveyDefinition> {
  return request<SurveyDefinition>(`/health-profiles/questions?kind=${encodeURIComponent(kind)}`)
}

/** 3-1 설문 저장. 201 (예측 결과 포함) */
export function postHealthProfile(body: HealthProfileRequest): Promise<CreateHealthProfileResponse> {
  return request<CreateHealthProfileResponse>('/health-profiles', { method: 'POST', body: JSON.stringify(body) })
}
