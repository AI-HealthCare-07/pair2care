// frontend/src/records/riskTrend.ts
// 기록 탭 위험도 추이 카드(Figma M07 "고혈압 위험도 추이") 규칙 — 순수 함수
//  - "낮아졌어요"는 직전 점보다 점수가 실제로 내려갔을 때만, 달라진 응답과 같이 (REQ-NFR-003, api.md 7-1)
//  - 인과 표현("~해서 낮아졌어요")은 쓰지 않고, 달라진 응답을 나란히 보여 줌

import type { ChangedInput, ModelPredictionDetail, CheckupPredictionDetail } from '../api/predictions'
import type { TrendPoint } from '../api/dashboard'
import { SURVEY_DEFINITION_ONBOARDING } from '../survey/definition'

export const TREND_WEEKS = 4 // Figma M07: 1주차~4주차

/** "2026-11-16" → "11/16 주" */
export function weekLabel(weekStart: string): string {
  const [, month, day] = weekStart.split('-').map(Number)
  return `${month}/${day} 주`
}

/** 막대 높이 % (점수 0~100, 너무 낮아도 막대가 보이게 최소 6%) */
export function barPercent(score: number): number {
  return Math.max(6, Math.min(100, score))
}

/** 마지막 점이 바로 앞 점보다 낮으면 그 예측 id (5-3에서 달라진 응답을 읽음), 아니면 null */
export function droppedPrediction(points: TrendPoint[]): number | null {
  if (points.length < 2) return null
  const [before, last] = points.slice(-2)
  return last.score < before.score ? last.prediction_id : null
}

/**
 * "낮아졌어요" 문구. 막대는 주별 마지막 점끼리라, 5-3 changed_inputs의 기준(직전 예측 previous)과 어긋날 수 있음
 * 예) 1주차 60 → 2주차 WEEKLY 50 → 같은 주 EDIT 58: 막대는 60→58(내려감)인데 응답은 50→58(올라감)
 * → 문구와 응답 기준을 맞추려고 previous보다도 낮을 때만 띄움 (#147 현영 님 리뷰, REQ-NFR-003)
 */
export function dropNote(detail: ModelPredictionDetail | CheckupPredictionDetail): string | null {
  if (detail.method !== 'MODEL' || detail.previous?.score == null || detail.score >= detail.previous.score) return null
  const changes = changedInputText(detail.changed_inputs ?? [])
  return changes ? `달라진 응답: ${changes}` : null
}

// changed_inputs에 오는 설문 값 11개 (서버 SURVEY_INPUT_FIELDS)의 짧은 이름
const INPUT_NAME: Record<string, string> = {
  height_cm: '키',
  weight_kg: '체중',
  father_diabetes_history: '아버지 당뇨',
  mother_diabetes_history: '어머니 당뇨',
  sibling_diabetes_history: '형제자매 당뇨',
  father_hypertension_history: '아버지 고혈압',
  mother_hypertension_history: '어머니 고혈압',
  sibling_hypertension_history: '형제자매 고혈압',
  alcohol_frequency: '술 마시는 횟수',
  alcohol_amount: '한 번에 마시는 양',
  smoking_current: '현재 흡연',
}
const UNIT: Record<string, string> = { height_cm: 'cm', weight_kg: 'kg' }

/** 값 하나를 설문 보기 문구로 (보기가 없는 키·체중은 숫자+단위) */
function answerText(field: string, value: ChangedInput['before']): string {
  if (value === null) return '응답 없음'
  const question = SURVEY_DEFINITION_ONBOARDING.questions.find((q) => q.field === field)
  const option = question?.options?.find((o) => o.value === value)
  if (option) return option.label
  return `${value}${UNIT[field] ?? ''}`
}

/** "체중 80 → 78.2kg · 술 마시는 횟수 주 2~3회 → 월 2~4회" (모르는 항목은 건너뜀) */
export function changedInputText(changes: ChangedInput[]): string {
  return changes
    .filter((change) => INPUT_NAME[change.feature])
    .map((change) => {
      const before = answerText(change.feature, change.before)
      const after = answerText(change.feature, change.after)
      // 숫자 항목은 단위를 뒤에 한 번만: "80 → 78.2kg"
      const unit = UNIT[change.feature]
      const shortBefore = unit && before.endsWith(unit) ? before.slice(0, -unit.length) : before
      return `${INPUT_NAME[change.feature]} ${shortBefore} → ${after}`
    })
    .join(' · ')
}
