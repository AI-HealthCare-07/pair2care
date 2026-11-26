// frontend/src/prediction/view.ts
// 5-2 응답 → S-09가 그릴 화면 상태. 화면 컴포넌트는 이 결과만 보고 그림 (API 규칙 해석은 여기 한 곳에서).

import { ApiError } from '../api/client'
import type { Disease, Factor, LatestPrediction, LatestPredictionsResponse, SkippedReason } from '../api/predictions'
import { DISEASE_ORDER, factorText, yearsText } from './labels'

export type DiseaseCard =
  | { kind: 'RESULT'; disease: Disease; model: LatestPrediction; checkup: LatestPrediction | null }
  | { kind: 'MANAGED'; disease: Disease } // 진단 "예" → 예측 안 함
  | { kind: 'MISSING'; disease: Disease } // 관리 중도 아닌데 모델 행이 없음 (그 질환만 예측 실패)

export type PredictionView =
  | { kind: 'GENERAL'; reason: SkippedReason } // M04-b 일반 안내
  | { kind: 'FAILED' } // 예측 실패: 5-2를 다시 불러도 그대로라 "다시 계산"(5-5) 버튼
  | { kind: 'RESULT'; cards: DiseaseCard[] } // M04

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
    return { kind: 'RESULT', disease, model, checkup: rows.find((p) => p.method === 'CHECKUP_CRITERIA') ?? null }
  })
  return { kind: 'RESULT', cards }
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
