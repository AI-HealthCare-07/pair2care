// frontend/src/api/predictions.mock.ts
// 백엔드 없이 S-09를 만들 때 쓰는 가짜 예측 API (predictions.ts와 함수 이름·시그니처가 같음).
// 응답 모양은 api.md 5-2·5-3과 서버 views.py 그대로. 점수·요인·건강 나이는 화면 확인용 가짜 값.
// 요인 예시는 #121에서 진짜 v1 모델로 계산한 45세 남성 당뇨 결과(아버지 가족력 +5 → bmi +3 …)를 따름.
// years: 조회 때 계산한 가감 나이. means_by_sex가 없거나 예전 행이면 null (similar·health_age_null 경우)

import { ApiError } from './client'
import type {
  Disease,
  Factor,
  HealthAge,
  LatestPrediction,
  LatestPredictionsResponse,
  ModelPredictionDetail,
  PredictionDetail,
  RiskLevel,
} from './predictions'
import { MOCK_PREDICTION_SCENARIOS, type MockPredictionScenario } from './predictions.mockScenarios'

let delayMs = 250 // 로딩 화면 확인용. 테스트는 0
const wait = () => new Promise<void>((resolve) => setTimeout(resolve, delayMs))
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T

const CREATED_AT = '2026-11-19T10:40:00+09:00'
const PREVIOUS_AT = '2026-11-12T09:10:00+09:00'

let scenario: MockPredictionScenario = 'normal'
// failed에서 "다시 계산"이 성공하면 true → 그 뒤 5-2·5-3은 normal 결과. 다른 경우로 바꾸면 처음 상태로
let recovered = false

/** 응답 지연(ms). 테스트에서 0으로 */
export function setMockPredictionDelay(ms: number) {
  delayMs = ms
}

/** 가짜 응답 경우 바꾸기 (predictionsApi.setMockScenario로 부름). 모르는 이름은 'normal' */
export function setMockPredictionScenario(next: string | null) {
  const known = (MOCK_PREDICTION_SCENARIOS as readonly string[]).includes(next ?? '') ? (next as MockPredictionScenario) : 'normal'
  if (known !== scenario) recovered = false // 화면이 다시 불러올 때마다 같은 이름으로 부르므로, 바뀔 때만 되돌림
  scenario = known
}

const current = (): MockPredictionScenario => (recovered ? 'normal' : scenario)

function modelRow(id: number, disease: Disease, score: number, level: RiskLevel, health_age: HealthAge | null): LatestPrediction {
  return { id, disease, method: 'MODEL', score, level, health_age, created_at: CREATED_AT }
}

function modelDetail(row: LatestPrediction, factors: Factor[], withPrevious = false): ModelPredictionDetail {
  return {
    id: row.id,
    disease: row.disease,
    method: 'MODEL',
    score: row.score ?? 0,
    level: row.level,
    factors,
    model_version: row.disease === 'DIABETES' ? 'diabetes_risk:v1' : 'hypertension_risk:v1',
    changed_inputs: withPrevious ? [{ feature: 'weight_kg', before: 80.0, after: 78.2 }] : null,
    previous: withPrevious ? { id: row.id - 20, score: (row.score ?? 0) + 3, level: row.level, created_at: PREVIOUS_AT } : null,
    health_age: row.health_age,
    created_at: CREATED_AT,
  }
}

const AGE = (decade: number | null, out_of_range: HealthAge['out_of_range'] = null, actual_age = 45): HealthAge => ({
  decade,
  actual_age,
  out_of_range,
})

interface MockData {
  latest: LatestPredictionsResponse | 'NO_SURVEY'
  details: PredictionDetail[]
}

function build(name: MockPredictionScenario): MockData {
  const empty = (overrides: Partial<LatestPredictionsResponse> = {}): LatestPredictionsResponse => ({
    health_profile_id: 31,
    predictions: [],
    managed_diseases: [],
    skipped_reason: null,
    metabolic_syndrome: null,
    ...overrides,
  })

  switch (name) {
    case 'normal': {
      const dm = modelRow(51, 'DIABETES', 18, 'LOW', AGE(null, 'BELOW'))
      const htn = modelRow(52, 'HYPERTENSION', 45, 'CAUTION', AGE(50))
      return {
        latest: empty({ predictions: [dm, htn] }),
        details: [
          modelDetail(dm, [
            { feature: 'father_diabetes_history', direction: 'UP', years: 5 },
            { feature: 'bmi', direction: 'UP', years: 3 },
            { feature: 'smoking_current', direction: 'DOWN', years: -2 },
          ], true),
          modelDetail(htn, [
            { feature: 'bmi', direction: 'UP', years: 4 },
            { feature: 'mother_hypertension_history', direction: 'UP', years: 3 },
            { feature: 'alcohol_frequency', direction: 'UP', years: 1 },
          ], true),
        ],
      }
    }
    case 'similar': {
      const dm = modelRow(61, 'DIABETES', 72, 'HIGH', AGE(null, 'ABOVE', 58))
      const htn = modelRow(62, 'HYPERTENSION', 22, 'LOW', AGE(40, null, 43))
      return {
        latest: empty({ predictions: [dm, htn] }),
        details: [
          // age는 #107 전에 저장된 행처럼 섞어 둠 → 화면은 건너뛰어야 함
          modelDetail(dm, [{ feature: 'age', direction: 'UP', years: null }, { feature: 'bmi', direction: 'UP', years: null }]),
          modelDetail(htn, []),
        ],
      }
    }
    case 'health_age_null': {
      const dm = modelRow(71, 'DIABETES', 34, 'CAUTION', null)
      const htn = modelRow(72, 'HYPERTENSION', 21, 'LOW', null)
      return {
        latest: empty({ predictions: [dm, htn] }),
        details: [
          modelDetail(dm, [
            { feature: 'bmi', direction: 'UP', years: null },
            { feature: 'alcohol_amount', direction: 'DOWN', years: null },
          ]),
          modelDetail(htn, [{ feature: 'sibling_hypertension_history', direction: 'DOWN', years: null }]),
        ],
      }
    }
    case 'managed_one': {
      const htn = modelRow(82, 'HYPERTENSION', 31, 'CAUTION', AGE(40))
      return {
        latest: empty({ predictions: [htn], managed_diseases: ['DIABETES'] }),
        details: [modelDetail(htn, [{ feature: 'bmi', direction: 'UP', years: 2 }, { feature: 'alcohol_amount', direction: 'UP', years: 1 }])],
      }
    }
    case 'managed_both':
      return { latest: empty({ managed_diseases: ['DIABETES', 'HYPERTENSION'] }), details: [] }
    case 'pregnant':
      return { latest: empty({ skipped_reason: 'PREGNANT' }), details: [] }
    case 'age_out':
      return { latest: empty({ skipped_reason: 'AGE_OUT_OF_RANGE' }), details: [] }
    case 'failed':
    case 'failed_again':
      return { latest: empty(), details: [] }
    case 'partial_failed': {
      const htn = modelRow(92, 'HYPERTENSION', 45, 'CAUTION', AGE(50))
      return {
        latest: empty({ predictions: [htn] }),
        details: [modelDetail(htn, [{ feature: 'bmi', direction: 'UP', years: 3 }])],
      }
    }
    case 'checkup': {
      const dm = modelRow(101, 'DIABETES', 18, 'LOW', AGE(40))
      const htn = modelRow(102, 'HYPERTENSION', 45, 'CAUTION', AGE(50))
      const htnCheckup: LatestPrediction = {
        id: 103,
        disease: 'HYPERTENSION',
        method: 'CHECKUP_CRITERIA',
        score: null,
        level: 'CAUTION',
        checkup_record_id: 8,
        health_age: null,
        created_at: CREATED_AT,
      }
      return {
        latest: empty({
          predictions: [dm, htn, htnCheckup],
          metabolic_syndrome: { status: 'UNKNOWN', met_count: 2, missing: ['triglyceride', 'hdl_cholesterol'] },
        }),
        details: [
          modelDetail(dm, [{ feature: 'bmi', direction: 'UP', years: 2 }]),
          modelDetail(htn, [{ feature: 'father_hypertension_history', direction: 'UP', years: 4 }, { feature: 'bmi', direction: 'UP', years: 2 }]),
          {
            id: 103,
            disease: 'HYPERTENSION',
            method: 'CHECKUP_CRITERIA',
            score: null,
            level: 'CAUTION',
            factors: null,
            model_version: null,
            changed_inputs: null,
            previous: null,
            health_age: null,
            used_values: { systolic_bp: 134, diastolic_bp: 86 },
            checked_on: '2026-05-10',
            created_at: CREATED_AT,
          },
        ],
      }
    }
    case 'checkup_met': {
      const dm = modelRow(111, 'DIABETES', 34, 'CAUTION', AGE(50))
      const htn = modelRow(112, 'HYPERTENSION', 62, 'HIGH', AGE(60))
      const criteria = (id: number, disease: Disease, level: RiskLevel, used_values: Record<string, number>) => ({
        row: { id, disease, method: 'CHECKUP_CRITERIA', score: null, level, checkup_record_id: 9, health_age: null, created_at: CREATED_AT } as LatestPrediction,
        detail: {
          id, disease, method: 'CHECKUP_CRITERIA', score: null, level, factors: null, model_version: null,
          changed_inputs: null, previous: null, health_age: null, used_values, checked_on: '2026-09-02', created_at: CREATED_AT,
        } as PredictionDetail,
      })
      const dmCheckup = criteria(113, 'DIABETES', 'CAUTION', { fasting_glucose: 112 })
      const htnCheckup = criteria(114, 'HYPERTENSION', 'HIGH', { systolic_bp: 146, diastolic_bp: 92 })
      return {
        latest: empty({
          predictions: [dm, dmCheckup.row, htn, htnCheckup.row],
          metabolic_syndrome: { status: 'MET', met_count: 3, missing: ['hdl_cholesterol'] },
        }),
        details: [
          modelDetail(dm, [{ feature: 'bmi', direction: 'UP', years: 3 }]),
          dmCheckup.detail,
          modelDetail(htn, [{ feature: 'bmi', direction: 'UP', years: 4 }, { feature: 'alcohol_amount', direction: 'UP', years: 2 }]),
          htnCheckup.detail,
        ],
      }
    }
    case 'no_survey':
      return { latest: 'NO_SURVEY', details: [] }
  }
}

export async function getLatestPredictions(): Promise<LatestPredictionsResponse> {
  await wait()
  const { latest } = build(current())
  if (latest === 'NO_SURVEY') throw new ApiError(404, '아직 설문 기록이 없어요.')
  return clone(latest)
}

export async function getPrediction(id: number): Promise<PredictionDetail> {
  await wait()
  const found = build(current()).details.find((d) => d.id === id)
  if (!found) throw new ApiError(404, '예측 기록을 찾을 수 없어요.')
  return clone(found)
}

/** 5-5 다시 계산. failed → 성공(이후 normal), failed_again → 503, 설문 없음 → 404, 이미 결과가 있으면 409 (api.md 5-5) */
export async function retryPredictions(): Promise<void> {
  await wait()
  const { latest } = build(current())
  if (latest === 'NO_SURVEY') throw new ApiError(404, '아직 설문 기록이 없어요.')
  if (current() === 'failed_again') throw new ApiError(503, '위험도를 계산하지 못했어요. 잠시 후 다시 시도해 주세요.')
  if (current() !== 'failed') throw new ApiError(409, '이미 계산된 위험도가 있어요.')
  recovered = true
}
