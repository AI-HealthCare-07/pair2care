// frontend/src/survey/survey.test.ts
// 문항 정의(definition)·보일 문항 계산(visibleQuestions)·입력 검사와 3-1 요청 본문(payload)·3-1 에러 → 화면 동작
// 근거: api.md 3-1(건너뛰기·입력 규칙·에러 목록), 3-6(공통 필드)

import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { surveyErrorAction } from '../api/healthProfiles'
import { SURVEY_DEFINITION_ONBOARDING as DEF } from './definition'
import { buildSurveyRequest, validateAnswers } from './payload'
import { drinkerSmokerAnswers } from './testFixtures'
import type { Gender, SurveyAnswers, SurveyDefinition } from './types'
import { computeVisibility, pruneHiddenAnswers, questionText } from './visibleQuestions'

const visibleFields = (def: SurveyDefinition, answers: SurveyAnswers, gender?: Gender) =>
  computeVisibility(def, answers, gender).visible.map((q) => q.field)

const byField = (field: string) => {
  const q = DEF.questions.find((x) => x.field === field)
  if (!q) throw new Error(`문항 없음: ${field}`)
  return q
}

describe('문항 정의 (3-6과 같은 모양)', () => {
  it('v1.0, 가입 설문, 21문항이 1~21번 순서', () => {
    expect(DEF.survey_version).toBe('v1.0')
    expect(DEF.kind).toBe('ONBOARDING')
    expect(DEF.questions.map((q) => q.no)).toEqual(Array.from({ length: 21 }, (_, i) => i + 1))
  })

  it('field 이름이 겹치지 않음 (3-1 요청 키 21개)', () => {
    expect(new Set(DEF.questions.map((q) => q.field)).size).toBe(21)
  })

  it('14번 흡연 보기는 화면 순서 3/1/2 (피운 적 없음이 맨 위)', () => {
    expect(byField('smoking_lifetime').options?.map((o) => o.value)).toEqual([3, 1, 2])
  })

  it('보조 설명 help는 12번 음주량에만 있음', () => {
    expect(DEF.questions.filter((q) => q.help).map((q) => q.no)).toEqual([12])
  })

  it('임신 문항만 FEMALE 전용', () => {
    expect(DEF.questions.filter((q) => q.only_for).map((q) => [q.no, q.only_for])).toEqual([[21, 'FEMALE']])
  })

  it('NUMBER 범위가 3-1 입력 규칙과 같음 (체중 25~300, 허리둘레는 선택)', () => {
    expect(byField('weight_kg')).toMatchObject({ min: 25, max: 300, required: true })
    expect(byField('waist_cm').required).toBe(false)
    expect(byField('cigarettes_per_day')).toMatchObject({ min: 1, max: 60, step: 1 })
  })
})

describe('questionText (13번 성별 문구)', () => {
  const q13 = byField('binge_frequency')

  it('성별에 맞는 문구 (남 7잔·여 5잔)', () => {
    expect(questionText(q13, 'MALE')).toContain('7잔')
    expect(questionText(q13, 'FEMALE')).toContain('5잔')
  })

  it('성별을 모르면 기본 text', () => {
    expect(questionText(q13)).toBe(q13.text)
  })
})

describe('computeVisibility (화면에 보일 문항)', () => {
  it('남성은 20문항 (임신 숨김), 여성은 21문항', () => {
    expect(visibleFields(DEF, {}, 'MALE')).toHaveLength(20)
    expect(visibleFields(DEF, {}, 'MALE')).not.toContain('is_pregnant')
    expect(visibleFields(DEF, {}, 'FEMALE')).toHaveLength(21)
  })

  it('성별을 모르면 only_for 문항은 숨김', () => {
    expect(visibleFields(DEF, {})).not.toContain('is_pregnant')
  })

  it('10번 술 "없다"(1) → 11·12·13번 숨김', () => {
    const fields = visibleFields(DEF, { alcohol_ever: 1 }, 'MALE')
    expect(fields).not.toContain('alcohol_frequency')
    expect(fields).not.toContain('alcohol_amount')
    expect(fields).not.toContain('binge_frequency')
    expect(fields).toContain('smoking_lifetime')
  })

  it('11번 "전혀 마시지 않았다"(1) → 12·13번만 숨김', () => {
    const fields = visibleFields(DEF, { alcohol_ever: 2, alcohol_frequency: 1 }, 'MALE')
    expect(fields).toContain('alcohol_frequency')
    expect(fields).not.toContain('alcohol_amount')
    expect(fields).not.toContain('binge_frequency')
  })

  it('14번 "피운 적 없음"(3) → 15·16번 숨김, 15번 "과거에만"(3) → 16번만 숨김', () => {
    const never = visibleFields(DEF, { smoking_lifetime: 3 }, 'MALE')
    expect(never).not.toContain('smoking_current')
    expect(never).not.toContain('cigarettes_per_day')

    const quit = visibleFields(DEF, { smoking_lifetime: 2, smoking_current: 3 }, 'MALE')
    expect(quit).toContain('smoking_current')
    expect(quit).not.toContain('cigarettes_per_day')
  })

  it('사용자가 고른 보기 8(형제자매 없음·사용한 적 없음)은 아무것도 숨기지 않음', () => {
    const fields = visibleFields(DEF, { sibling_diabetes_history: 8, heated_tobacco: 8 }, 'MALE')
    expect(fields).toHaveLength(20)
  })

  it('숨겨진 문항의 답은 건너뛰기 규칙에 쓰지 않음', () => {
    // A가 B를 숨기고, B의 답이 C를 숨기는 규칙이 있어도 B가 숨겨졌으면 C는 보임
    const def: SurveyDefinition = {
      survey_version: 't',
      kind: 'ONBOARDING',
      questions: [
        { no: 1, field: 'a', text: 'A', type: 'SINGLE', options: [{ label: '1', value: 1 }], skip: [{ when: 1, fields: ['b'] }] },
        { no: 2, field: 'b', text: 'B', type: 'SINGLE', options: [{ label: '1', value: 1 }], skip: [{ when: 1, fields: ['c'] }] },
        { no: 3, field: 'c', text: 'C', type: 'SINGLE', options: [{ label: '1', value: 1 }] },
      ],
    }
    expect(visibleFields(def, { a: 1, b: 1 })).toEqual(['a', 'c'])
  })

  it('WEEKLY에서 ask_when_applicable === false인 문항은 숨김, ONBOARDING에서는 무시', () => {
    const questions = [
      { no: 1, field: 'x', text: 'X', type: 'BOOLEAN' as const, ask_when_applicable: false },
      { no: 2, field: 'y', text: 'Y', type: 'BOOLEAN' as const, ask_when_applicable: true },
    ]
    expect(visibleFields({ survey_version: 't', kind: 'WEEKLY', questions }, {})).toEqual(['y'])
    expect(visibleFields({ survey_version: 't', kind: 'ONBOARDING', questions }, {})).toEqual(['x', 'y'])
  })
})

describe('pruneHiddenAnswers (숨겨진 답 지우기)', () => {
  it('10번을 "없다"로 바꾸면 11~13번 답이 지워지고 나머지는 남음', () => {
    const before = drinkerSmokerAnswers()
    const after = pruneHiddenAnswers(DEF, { ...before, alcohol_ever: 1 }, 'MALE')
    expect(after).not.toHaveProperty('alcohol_frequency')
    expect(after).not.toHaveProperty('alcohol_amount')
    expect(after).not.toHaveProperty('binge_frequency')
    expect(after.alcohol_ever).toBe(1)
    expect(after.smoking_current).toBe(1)
  })

  it('남성에게 남은 임신 답은 지움', () => {
    const after = pruneHiddenAnswers(DEF, { ...drinkerSmokerAnswers(), is_pregnant: true }, 'MALE')
    expect(after).not.toHaveProperty('is_pregnant')
  })

  it('넘겨받은 답 객체를 바꾸지 않음', () => {
    const before: SurveyAnswers = { ...drinkerSmokerAnswers(), alcohol_ever: 1 }
    pruneHiddenAnswers(DEF, before, 'MALE')
    expect(before.alcohol_frequency).toBe(4)
  })
})

describe('validateAnswers (제출 전 전체 검사)', () => {
  it('아무것도 안 답한 남성: 보이는 필수 19개가 문항 순서대로 (허리둘레 제외)', () => {
    const errors = validateAnswers(DEF, {}, 'MALE')
    expect(errors).toHaveLength(19)
    expect(errors[0].field).toBe('height_cm')
    expect(errors.map((e) => e.field)).not.toContain('waist_cm')
  })

  it('다 답하면 오류 없음', () => {
    expect(validateAnswers(DEF, drinkerSmokerAnswers(), 'MALE')).toEqual([])
  })

  it('체중 경계값: 25·300은 통과, 24.9·300.1은 범위 안내', () => {
    const check = (w: number) => validateAnswers(DEF, { ...drinkerSmokerAnswers(), weight_kg: w }, 'MALE')
    expect(check(25)).toEqual([])
    expect(check(300)).toEqual([])
    expect(check(24.9)).toEqual([{ field: 'weight_kg', message: '25~300kg 사이로 입력해 주세요.' }])
    expect(check(300.1)).toHaveLength(1)
  })

  it('하루 개비는 정수만, 숫자가 아니면 숫자 안내', () => {
    const base = drinkerSmokerAnswers()
    expect(validateAnswers(DEF, { ...base, cigarettes_per_day: 1.5 }, 'MALE')[0].message).toBe('정수로 입력해 주세요.')
    expect(validateAnswers(DEF, { ...base, height_cm: Number.NaN }, 'MALE')[0].message).toBe('숫자를 입력해 주세요.')
  })

  it('허리둘레는 비워도 되지만, 적었으면 범위 검사', () => {
    const base = drinkerSmokerAnswers()
    expect(validateAnswers(DEF, { ...base, waist_cm: undefined }, 'MALE')).toEqual([])
    expect(validateAnswers(DEF, { ...base, waist_cm: 39 }, 'MALE')[0].field).toBe('waist_cm')
  })

  it('보기에 없는 값은 오류, 숨겨진 문항의 값은 검사하지 않음', () => {
    const base = drinkerSmokerAnswers()
    expect(validateAnswers(DEF, { ...base, alcohol_amount: 7 }, 'MALE')[0].message).toBe('보기에서 골라 주세요.')
    expect(validateAnswers(DEF, { ...base, alcohol_ever: 1, alcohol_amount: 7 }, 'MALE')).toEqual([])
  })
})

describe('buildSurveyRequest (3-1 요청 본문)', () => {
  it('kind·survey_version + 21문항 키를 모두 보냄', () => {
    const body = buildSurveyRequest(DEF, drinkerSmokerAnswers(), 'MALE')
    expect(body.kind).toBe('ONBOARDING')
    expect(body.survey_version).toBe('v1.0')
    expect(Object.keys(body)).toHaveLength(23)
  })

  it('건너뛴 문항은 null (8·888은 서버가 채움), 사용자가 고른 8은 그대로', () => {
    const body = buildSurveyRequest(
      DEF,
      { ...drinkerSmokerAnswers(), alcohol_ever: 1, smoking_lifetime: 3, alcohol_frequency: 4 },
      'MALE',
    )
    expect(body.alcohol_frequency).toBeNull()
    expect(body.alcohol_amount).toBeNull()
    expect(body.binge_frequency).toBeNull()
    expect(body.smoking_current).toBeNull()
    expect(body.cigarettes_per_day).toBeNull()
    expect(body.sibling_diabetes_history).toBe(8)
    expect(body.heated_tobacco).toBe(8)
  })

  it('남성 임신은 null, 안 적은 허리둘레는 null, 여성이 고른 false는 그대로', () => {
    const male = buildSurveyRequest(DEF, { ...drinkerSmokerAnswers(), waist_cm: undefined }, 'MALE')
    expect(male.is_pregnant).toBeNull()
    expect(male.waist_cm).toBeNull()

    const female = buildSurveyRequest(DEF, { ...drinkerSmokerAnswers(), is_pregnant: false }, 'FEMALE')
    expect(female.is_pregnant).toBe(false)
  })
})

describe('surveyErrorAction (3-1 에러 → 화면 동작)', () => {
  it.each([
    [new ApiError(409, '설문이 바뀌었어요.', 'SURVEY_VERSION_MISMATCH'), 'RELOAD_DEFINITION'],
    [new ApiError(409, '가입 설문 먼저', 'ONBOARDING_REQUIRED'), 'GO_ONBOARDING'],
    [new ApiError(409, '이미 했어요', 'ONBOARDING_ALREADY_DONE'), 'GO_HOME'],
    [new ApiError(400, '음주량을 확인해 주세요.', 'SURVEY_FIELD_INVALID', 'alcohol_amount'), 'FOCUS_FIELD'],
    [new ApiError(422, 'validation'), 'RECHECK_INPUT'],
    [new ApiError(401, '로그인이 필요해요.'), 'RELOGIN'],
    [new ApiError(500, '서버 오류'), 'SHOW_MESSAGE'],
    [new ApiError(409, '모르는 409', 'SOMETHING_ELSE'), 'SHOW_MESSAGE'],
  ])('%#: %s → %s', (err, action) => {
    expect(surveyErrorAction(err)).toBe(action)
  })
})
