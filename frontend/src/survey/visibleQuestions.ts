// frontend/src/survey/visibleQuestions.ts
// 지금까지의 답으로 "화면에 보일 문항"을 계산하는 순수 함수 (api.md 3-1 건너뛰기, 3-6 공통 필드).
//
// 숨기는 경우
//  1) only_for가 내 성별과 다름 (예: 임신은 FEMALE만). 성별을 모르면(undefined) only_for 문항은 숨김
//     → 화면은 users.gender를 받은 뒤에 이 함수를 써야 함
//  2) 앞 문항의 답이 skip.when에 걸려 fields에 들어감 (예: 10번 "없다" → 11~13)
//  3) kind=WEEKLY에서 ask_when_applicable === false (해당돼도 묻지 않음, 서버가 직전 값 복사)
// 숨겨진 문항의 답은 쓰지 않음(건너뛰기 규칙도 숨겨진 문항에서는 적용 안 함) → 문항 순서(questions 배열)대로 계산

import type { Gender, Question, SurveyAnswers, SurveyDefinition } from './types'

export interface Visibility {
  visible: Question[]
  hiddenFields: Set<string>
}

/** 성별에 맞는 문구 (text_by_gender가 있으면 그것, 없거나 성별을 모르면 text) */
export function questionText(question: Question, gender?: Gender): string {
  return (gender && question.text_by_gender?.[gender]) || question.text
}

export function computeVisibility(def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender): Visibility {
  const skipped = new Set<string>()
  const hiddenFields = new Set<string>()
  const visible: Question[] = []

  for (const q of def.questions) {
    const hidden =
      skipped.has(q.field) ||
      (q.only_for !== undefined && q.only_for !== gender) ||
      (def.kind === 'WEEKLY' && q.ask_when_applicable === false)

    if (hidden) {
      hiddenFields.add(q.field)
      continue
    }
    visible.push(q)

    const answer = answers[q.field]
    if (answer === undefined || answer === null) continue
    for (const rule of q.skip ?? []) {
      if (answer === rule.when) rule.fields.forEach((f) => skipped.add(f))
    }
  }
  return { visible, hiddenFields }
}

/**
 * 숨겨진 문항의 답을 지운 새 답 객체. 앞 문항을 바꿔서 뒤 문항이 숨겨질 때 이미 입력한 답이
 * 남아 있으면 3-1이 400(건너뛸 문항인데 값이 옴)을 주므로, 답을 바꿀 때마다 거치는 걸 권장.
 */
export function pruneHiddenAnswers(def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender): SurveyAnswers {
  const { hiddenFields } = computeVisibility(def, answers, gender)
  const next: SurveyAnswers = {}
  for (const [field, value] of Object.entries(answers)) {
    if (!hiddenFields.has(field)) next[field] = value
  }
  return next
}
