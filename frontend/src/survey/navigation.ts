// frontend/src/survey/navigation.ts
// 한 화면에 한 문항(와이어프레임 S-06)에서 쓰는 "다음/이전 문항 찾기"와 진행률.
// 보일 문항은 visibleQuestions.ts의 computeVisibility로 계산 (건너뛰기·성별 조건 반영).

import { computeVisibility } from './visibleQuestions'
import type { Gender, Question, SurveyAnswers, SurveyDefinition } from './types'

/** 지금 답 기준으로 보일 문항 중 맨 처음 문항 */
export function firstQuestion(def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender): Question | null {
  return computeVisibility(def, answers, gender).visible[0] ?? null
}

/**
 * 현재 문항 다음에 보일 문항. 없으면 null(= 마지막이라 제출).
 * 현재 문항이 숨겨진 상태여도(예: 앞 문항을 고쳐서) 정의 순서 기준으로 그 뒤의 첫 보일 문항을 줌.
 */
export function nextQuestion(def: SurveyDefinition, answers: SurveyAnswers, currentField: string, gender?: Gender): Question | null {
  const order = def.questions.map((q) => q.field)
  const pos = order.indexOf(currentField)
  return computeVisibility(def, answers, gender).visible.find((q) => order.indexOf(q.field) > pos) ?? null
}

/** 현재 문항 앞에 보일 문항(이전 버튼). 없으면 null(= 첫 문항이라 "이전" 숨김) */
export function previousQuestion(def: SurveyDefinition, answers: SurveyAnswers, currentField: string, gender?: Gender): Question | null {
  const order = def.questions.map((q) => q.field)
  const pos = order.indexOf(currentField)
  const before = computeVisibility(def, answers, gender).visible.filter((q) => order.indexOf(q.field) < pos)
  return before[before.length - 1] ?? null
}

/**
 * 진행률(%) = 보일 문항 중 현재 문항 앞에 있는 문항 수 ÷ 보일 문항 수 (와이어프레임: "n/21"이 아니라 남은 문항 기준 %).
 * 건너뛰기로 보일 문항이 줄면 분모가 줄어 퍼센트가 뛸 수 있음. 첫 문항 0%, 제출 성공 뒤에 100%.
 * 현재 문항이 보일 목록에 없으면(숨겨진 상태) 정의 순서상 앞에 있는 보일 문항 수로 계산.
 */
export function progressPercent(def: SurveyDefinition, answers: SurveyAnswers, currentField: string, gender?: Gender): number {
  const { visible } = computeVisibility(def, answers, gender)
  if (visible.length === 0) return 100
  const order = def.questions.map((q) => q.field)
  const pos = order.indexOf(currentField)
  const before = visible.filter((q) => order.indexOf(q.field) < pos).length
  return Math.round((before / visible.length) * 100)
}
