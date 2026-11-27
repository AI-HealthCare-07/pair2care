// frontend/src/prediction/view.ts
// 5-2 응답 → S-09가 그릴 화면 상태. 화면 컴포넌트는 이 결과만 보고 그림 (API 규칙 해석은 여기 한 곳에서).

import { ApiError } from '../api/client'
import type {
  Disease,
  Factor,
  LatestPrediction,
  LatestPredictionsResponse,
  MetabolicSyndrome,
  SkippedReason,
} from '../api/predictions'
import type { CheckupKey } from '../checkup/checkupFields'
import { DISEASE_ORDER, factorText, METABOLIC_CRITERION_LABEL, type MetabolicStatus, yearsText } from './labels'

/**
 * 질환 카드의 S-07 링크 (기준표 행이 없을 때만). focus = S-07에서 바로 갈 입력칸 (#153 ?focus=)
 *  - NONE: 유효한 검진이 없음(metabolic_syndrome null = 검진 없음 또는 1년 지남) → 그 질환 첫 칸
 *  - MORE: 유효한 검진은 있는데 이 질환 판정이 안 됨 = 있는 값은 정상이고 항목이 빠짐 (api.md 5-1)
 */
export interface CheckupPrompt {
  kind: 'NONE' | 'MORE'
  focus: CheckupKey
}

export type DiseaseCard =
  | { kind: 'RESULT'; disease: Disease; model: LatestPrediction; checkup: LatestPrediction | null; prompt: CheckupPrompt | null }
  | { kind: 'MANAGED'; disease: Disease } // 진단 "예" → 예측 안 함
  | { kind: 'MISSING'; disease: Disease } // 관리 중도 아닌데 모델 행이 없음 (그 질환만 예측 실패)

export type PredictionView =
  | { kind: 'GENERAL'; reason: SkippedReason } // M04-b 일반 안내
  | { kind: 'FAILED' } // 예측 실패: 5-2를 다시 불러도 그대로라 "다시 계산"(5-5) 버튼
  | { kind: 'RESULT'; cards: DiseaseCard[]; metabolic: MetabolicView | null } // M04

/**
 * 판단 순서
 *  1. skipped_reason(임신·나이 범위 밖) → 일반 안내
 *  2. predictions·managed_diseases 둘 다 비어 있음 → 예측 실패 (현영 님 11/25 규칙)
 *  3. 그 외 → 질환별 카드 (고혈압 → 당뇨). 질환마다 결과 / 관리 중 / 계산 못 함
 */
export function buildPredictionView(latest: LatestPredictionsResponse): PredictionView {
  if (latest.skipped_reason) return { kind: 'GENERAL', reason: latest.skipped_reason }
  if (latest.predictions.length === 0 && latest.managed_diseases.length === 0) return { kind: 'FAILED' }

  const cards = DISEASE_ORDER.map((disease): DiseaseCard => {
    if (latest.managed_diseases.includes(disease)) return { kind: 'MANAGED', disease }
    const rows = latest.predictions.filter((p) => p.disease === disease)
    const model = rows.find((p) => p.method === 'MODEL')
    if (!model) return { kind: 'MISSING', disease }
    const checkup = rows.find((p) => p.method === 'CHECKUP_CRITERIA') ?? null
    return { kind: 'RESULT', disease, model, checkup, prompt: checkup ? null : checkupPrompt(disease, latest.metabolic_syndrome) }
  })
  return { kind: 'RESULT', cards, metabolic: metabolicView(latest.metabolic_syndrome) }
}

/**
 * 기준표 행이 없는 질환에서 S-07 어느 칸으로 보낼지.
 * 5-2에는 검진 값이 없어서 metabolic_syndrome으로 짐작함 (같은 검진 1건·같은 1년 기준이라 맞음, api.md 5-1):
 *  - null → 유효한 검진 없음 → NONE (고혈압 수축기 / 당뇨 공복혈당)
 *  - 고혈압 MORE → 수축기·이완기 중 하나가 빠짐. 어느 쪽인지는 몰라서 수축기 (두 칸이 한 줄에 같이 있음)
 *  - 당뇨 MORE → 공복혈당이 missing이면 공복혈당, 아니면 공복혈당은 있고 당화혈색소가 빠진 것
 *    (당뇨 카드가 RESULT면 진단 "예"가 아니라 공복혈당 기준은 값으로만 판정 → missing = 값 없음)
 */
export function checkupPrompt(disease: Disease, metabolic: MetabolicSyndrome | null): CheckupPrompt {
  if (!metabolic) return { kind: 'NONE', focus: disease === 'HYPERTENSION' ? 'systolic_bp' : 'fasting_glucose' }
  if (disease === 'HYPERTENSION') return { kind: 'MORE', focus: 'systolic_bp' }
  return { kind: 'MORE', focus: metabolic.missing.includes('fasting_glucose') ? 'fasting_glucose' : 'hba1c' }
}

/** 대사증후군 기준 이름(서버 criteria.py) → S-07 입력칸. 혈압은 수축기·이완기가 한 줄이라 수축기 */
const METABOLIC_CRITERION_FIELD: Record<string, CheckupKey> = {
  waist: 'waist_cm',
  triglyceride: 'triglyceride',
  hdl_cholesterol: 'hdl_cholesterol',
  blood_pressure: 'systolic_bp',
  fasting_glucose: 'fasting_glucose',
}

export interface MetabolicView {
  status: MetabolicStatus
  metCount: number
  missingLabels: string[] // 화면 이름 (중성지방·HDL), 모르는 기준 이름은 뺌
  focus: CheckupKey | null // 판단 어려움일 때만 첫 빠진 칸으로 (해당·해당 아님은 링크 없음)
}

/** 5-2 metabolic_syndrome → 카드. null(유효한 검진 없음)이면 카드 숨김 (wireframe.md S-09) */
export function metabolicView(metabolic: MetabolicSyndrome | null): MetabolicView | null {
  if (!metabolic) return null
  const known = metabolic.missing.filter((name) => name in METABOLIC_CRITERION_FIELD)
  return {
    status: metabolic.status,
    metCount: metabolic.met_count,
    missingLabels: known.map((name) => METABOLIC_CRITERION_LABEL[name]),
    focus: metabolic.status === 'UNKNOWN' && known.length > 0 ? METABOLIC_CRITERION_FIELD[known[0]] : null,
  }
}

/** S-07 링크 주소 (#153: 접힌 칸이면 펼치고 그 칸으로 이동) */
export function checkupLink(focus: CheckupKey): string {
  return `/checkup?focus=${focus}`
}

/**
 * 단계 기준 (api.md 5-0, 서버 model.py 상수와 같음): 30 미만 LOW / 30–59 CAUTION / 60 이상 HIGH.
 * 게이지의 색 구간과 낮음·주의·높음 글자 위치를 이 기준에 맞춰서, 62점(HIGH) 원이 "주의" 글자 옆에 찍히지 않게 함 (#111 성은 님)
 */
export const CAUTION_MIN_SCORE = 30
export const HIGH_MIN_SCORE = 60

/** 낮음·주의·높음 글자 위치(%): 각 구간의 가운데 → 15 · 45 · 80 */
export const GAUGE_LABEL_PERCENT = {
  LOW: CAUTION_MIN_SCORE / 2,
  CAUTION: (CAUTION_MIN_SCORE + HIGH_MIN_SCORE) / 2,
  HIGH: (HIGH_MIN_SCORE + 100) / 2,
} as const

/** 게이지 표시 위치 0~100(%). 기준표 행처럼 점수가 없으면 null */
export function gaugePercent(score: number | null): number | null {
  if (score === null || !Number.isFinite(score)) return null
  return Math.min(100, Math.max(0, score))
}

export interface FactorLine {
  feature: string
  direction: Factor['direction']
  text: string
  years: string | null // "+5살" · "−1살", 없으면 null (숫자 숨김)
}

/** 요인 → 화면 줄. 모르는 feature는 건너뜀, 최대 3개 (빈 배열이면 화면에서 요인 부분 숨김) */
export function factorLines(factors: Factor[] | null): FactorLine[] {
  const lines: FactorLine[] = []
  for (const factor of factors ?? []) {
    const text = factorText(factor)
    if (text) lines.push({ feature: factor.feature, direction: factor.direction, text, years: yearsText(factor.years) })
  }
  return lines.slice(0, 3)
}

/**
 * 5-5 다시 계산이 실패했을 때 화면이 할 일 (api.md 5-5)
 *  - 409 이미 계산됨(다른 탭·두 번 누름) → 5-2 다시 불러오기 (200과 같음)
 *  - 404 설문 없음 → 설문
 *  - 503 또 실패 · 시간 초과 · 연결 끊김 등 → 실패 화면 그대로 + 안내 문구
 *  - 401(세션 만료)은 따로 처리하지 않음: 가드가 보던 화면(from)을 담아 /login으로 보냄 (#134)
 */
export type RetryFailureAction = 'RELOAD' | 'ONBOARDING' | 'STAY_FAILED'

export function retryFailureAction(err: unknown): RetryFailureAction {
  if (!(err instanceof ApiError)) return 'STAY_FAILED'
  if (err.status === 409) return 'RELOAD'
  if (err.status === 404) return 'ONBOARDING'
  return 'STAY_FAILED'
}
