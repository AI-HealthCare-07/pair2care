// frontend/src/api/predictions.ts
// api.md 5장: 5-2 최근 예측(GET /risk-predictions/latest), 5-3 예측 상세(GET /risk-predictions/{id})
// 필드 이름·null 규칙은 서버 views.py(summarize_row·build_detail) 그대로. 화면은 predictionsApi.ts를 통해 부름.

import { apiFetch, toApiError } from './client'
import type { Disease } from './healthProfiles'

export type { Disease }
export type RiskLevel = 'LOW' | 'CAUTION' | 'HIGH'
export type PredictionMethod = 'MODEL' | 'CHECKUP_CRITERIA'
export type SkippedReason = 'PREGNANT' | 'AGE_OUT_OF_RANGE'

/**
 * 건강 나이 (5-2·5-3, #102). decade와 out_of_range는 둘 중 하나만 값이 있음.
 * 행 자체가 null인 경우: 기준표 행, 모델 JSON에 곡선 없음, 곡선 읽기 실패, model_version 다름
 * (#110부터 진짜 모델 JSON에 곡선이 있어서 모델 행은 보통 값이 옴)
 */
export interface HealthAge {
  decade: number | null // 40 = "40대 수준"
  actual_age: number // 예측할 때 만 나이
  out_of_range: 'BELOW' | 'ABOVE' | null // BELOW = 30세 미만, ABOVE = 69세 초과
}

/** 5-2 predictions 한 줄. 서버는 당뇨 → 고혈압, MODEL → 기준표 순서로 줌 (화면 순서는 prediction/view.ts에서 정함) */
export interface LatestPrediction {
  id: number
  disease: Disease
  method: PredictionMethod
  score: number | null // 기준표 행은 null
  level: RiskLevel
  checkup_record_id?: number // 기준표 행에만 있음
  health_age: HealthAge | null // 모든 행에 키가 있음 (기준표 행은 항상 null)
  created_at: string
}

export interface MetabolicSyndrome {
  status: 'MET' | 'NOT_MET' | 'UNKNOWN'
  met_count: number
  missing: string[] // 값이 없어 판단 못 한 기준 (예: triglyceride, hdl_cholesterol)
}

/** 5-2 응답 */
export interface LatestPredictionsResponse {
  health_profile_id: number
  predictions: LatestPrediction[]
  managed_diseases: Disease[] // 진단 "예" → 예측 안 함
  skipped_reason: SkippedReason | null
  metabolic_syndrome: MetabolicSyndrome | null // 유효한 검진이 없으면 null
}

/**
 * 요인 (5-3). UP = 위험을 높이는 쪽.
 * years: 같은 성별 평균인 사람보다 건강 나이를 몇 살 올리거나 내리는지 (정수, 0살은 서버가 뺌, #114·#121).
 *        means_by_sex를 못 쓰거나 예전 모델 행이면 null(방향만) → 화면은 숫자를 숨김. 예전 응답처럼 키가 없을 수도 있음
 */
export interface Factor {
  feature: string // bmi · father_diabetes_history … (모르는 값은 화면에서 건너뜀)
  direction: 'UP' | 'DOWN'
  years?: number | null
}

export interface ChangedInput {
  feature: string
  before: number | boolean | null
  after: number | boolean | null
}

export interface PreviousPrediction {
  id: number
  score: number | null
  level: RiskLevel
  created_at: string
}

interface PredictionDetailBase {
  id: number
  disease: Disease
  level: RiskLevel
  model_version: string | null
  created_at: string
}

/** 5-3 모델 행. 직전 예측이 없으면 changed_inputs·previous는 null */
export interface ModelPredictionDetail extends PredictionDetailBase {
  method: 'MODEL'
  score: number
  factors: Factor[] // 0~3개
  changed_inputs: ChangedInput[] | null
  previous: PreviousPrediction | null
  health_age: HealthAge | null
}

/** 5-3 기준표 행. 판정에 쓴 수치와 검진 날짜 (views.py: 최상위 키 used_values·checked_on) */
export interface CheckupPredictionDetail extends PredictionDetailBase {
  method: 'CHECKUP_CRITERIA'
  score: null
  factors: null
  changed_inputs: null
  previous: null
  health_age: null
  used_values: Record<string, number>
  checked_on: string | null
}

export type PredictionDetail = ModelPredictionDetail | CheckupPredictionDetail

async function request<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  if (!res.ok) throw await toApiError(res) // 5-2: 설문 없음 404 / 5-3: 남의 것·없는 id 404
  return (await res.json()) as T
}

/** 5-2 최근 예측. 설문이 없으면 404 ApiError */
export function getLatestPredictions(): Promise<LatestPredictionsResponse> {
  return request<LatestPredictionsResponse>('/risk-predictions/latest')
}

/** 5-3 예측 상세 */
export function getPrediction(id: number): Promise<PredictionDetail> {
  return request<PredictionDetail>(`/risk-predictions/${encodeURIComponent(String(id))}`)
}
