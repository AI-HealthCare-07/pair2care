// frontend/src/survey/payload.ts
// 제출 전 입력 검사, 그리고 3-1 저장 요청 본문 만들기.
//
// 서버는 오류를 "첫 번째 하나만" 돌려주므로(api.md 3-1 에러 목록), 제출 전에 여기서 전부 검사해
// 사용자가 에러를 하나씩 만나지 않게 함. 서버 검사(400·422)를 대신하는 건 아니고 정상 흐름에서 안 나오게 하는 용도.

import { computeVisibility } from './visibleQuestions'
import type { Gender, HealthProfileRequest, Question, SurveyAnswers, SurveyDefinition } from './types'

export interface AnswerError {
  field: string
  message: string
}

function checkQuestion(q: Question, value: SurveyAnswers[string]): string | null {
  const empty = value === undefined || value === null

  if (q.type === 'NUMBER') {
    if (empty) return q.required ? '값을 입력해 주세요.' : null // 허리둘레처럼 선택이면 비워도 됨
    if (typeof value !== 'number' || !Number.isFinite(value)) return '숫자를 입력해 주세요.'
    const min = q.min
    const max = q.max
    if ((min !== undefined && value < min) || (max !== undefined && value > max)) {
      return `${min ?? ''}~${max ?? ''}${q.unit ?? ''} 사이로 입력해 주세요.`
    }
    if (q.step === 1 && !Number.isInteger(value)) return '정수로 입력해 주세요.'
    return null
  }

  // SINGLE·BOOLEAN: 화면에 보이면 필수
  if (empty) return '하나를 골라 주세요.'
  if (q.options && !q.options.some((o) => o.value === value)) return '보기에서 골라 주세요.'
  return null
}

/** 보이는 문항만 검사 (숨겨진 문항은 값이 있어도 무시). 문항 순서대로 모든 오류를 돌려줌 */
export function validateAnswers(def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender): AnswerError[] {
  const errors: AnswerError[] = []
  for (const q of computeVisibility(def, answers, gender).visible) {
    const message = checkQuestion(q, answers[q.field])
    if (message) errors.push({ field: q.field, message })
  }
  return errors
}

/**
 * 3-1 요청 본문. 정의에 있는 문항만 보냄.
 *  - 숨겨진 문항(건너뛰기·성별 조건·안 묻는 문항)은 null → 8·888은 서버가 채움 (클라이언트가 8·888을 직접 보내면 422)
 *  - 사용자가 고른 보기 값(예: 형제자매 없음 8, 사용한 적 없음 8)은 그대로
 *  - 선택 문항(허리둘레)을 안 적었으면 null
 * validateAnswers가 비어 있을 때만 쓰는 것을 전제로 함
 */
export function buildSurveyRequest(def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender): HealthProfileRequest {
  const { hiddenFields } = computeVisibility(def, answers, gender)
  const body: HealthProfileRequest = { kind: def.kind, survey_version: def.survey_version }
  for (const q of def.questions) {
    body[q.field] = hiddenFields.has(q.field) ? null : (answers[q.field] ?? null)
  }
  return body
}
