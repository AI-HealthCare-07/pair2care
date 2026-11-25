// frontend/src/survey/navigation.test.ts
// 한 화면 한 문항의 다음·이전·진행률 (와이어프레임 S-06, Figma M02 "N% · 남은 질문 기준")

import { describe, expect, it } from 'vitest'
import { SURVEY_DEFINITION_ONBOARDING as DEF } from './definition'
import { firstQuestion, nextQuestion, previousQuestion, progressPercent } from './navigation'
import { drinkerSmokerAnswers } from './testFixtures'
import type { SurveyDefinition } from './types'

describe('firstQuestion', () => {
  it('첫 문항은 키', () => {
    expect(firstQuestion(DEF, {}, 'MALE')?.field).toBe('height_cm')
  })

  it('보일 문항이 없으면 null', () => {
    const def: SurveyDefinition = {
      survey_version: 't',
      kind: 'ONBOARDING',
      questions: [{ no: 1, field: 'p', text: 'P', type: 'BOOLEAN', only_for: 'FEMALE' }],
    }
    expect(firstQuestion(def, {}, 'MALE')).toBeNull()
  })
})

describe('nextQuestion', () => {
  it('키 → 몸무게', () => {
    expect(nextQuestion(DEF, {}, 'height_cm', 'MALE')?.field).toBe('weight_kg')
  })

  it('10번 "있다" → 11번, "없다" → 14번 (11~13 건너뜀)', () => {
    expect(nextQuestion(DEF, { alcohol_ever: 2 }, 'alcohol_ever', 'MALE')?.field).toBe('alcohol_frequency')
    expect(nextQuestion(DEF, { alcohol_ever: 1 }, 'alcohol_ever', 'MALE')?.field).toBe('smoking_lifetime')
  })

  it('14번 "피운 적 없음" → 17번 (15·16 건너뜀)', () => {
    expect(nextQuestion(DEF, { smoking_lifetime: 3 }, 'smoking_lifetime', 'MALE')?.field).toBe('heated_tobacco')
  })

  it('마지막 문항: 남성은 20번 다음이 없음(완료), 여성은 21번 임신', () => {
    expect(nextQuestion(DEF, {}, 'is_diabetes_diagnosed', 'MALE')).toBeNull()
    expect(nextQuestion(DEF, {}, 'is_diabetes_diagnosed', 'FEMALE')?.field).toBe('is_pregnant')
    expect(nextQuestion(DEF, {}, 'is_pregnant', 'FEMALE')).toBeNull()
  })

  it('지금 문항이 숨겨진 상태여도 정의 순서상 다음 보일 문항으로', () => {
    // 12번에 있다가 앞의 10번을 "없다"로 바꾼 경우
    expect(nextQuestion(DEF, { alcohol_ever: 1 }, 'alcohol_amount', 'MALE')?.field).toBe('smoking_lifetime')
  })
})

describe('previousQuestion', () => {
  it('첫 문항은 이전이 없음 ("이전" 숨김)', () => {
    expect(previousQuestion(DEF, {}, 'height_cm', 'MALE')).toBeNull()
  })

  it('건너뛴 문항을 거치지 않고 돌아감 (14번 → 10번)', () => {
    expect(previousQuestion(DEF, { alcohol_ever: 1 }, 'smoking_lifetime', 'MALE')?.field).toBe('alcohol_ever')
    expect(previousQuestion(DEF, drinkerSmokerAnswers(), 'smoking_lifetime', 'MALE')?.field).toBe('binge_frequency')
  })
})

describe('progressPercent (남은 질문 기준 %)', () => {
  it('첫 문항 0%', () => {
    expect(progressPercent(DEF, {}, 'height_cm', 'MALE')).toBe(0)
  })

  it('남성 마지막(20번) = 19/20 = 95%', () => {
    expect(progressPercent(DEF, drinkerSmokerAnswers(), 'is_diabetes_diagnosed', 'MALE')).toBe(95)
  })

  it('건너뛰면 분모가 줄어 퍼센트가 뜀 (14번: 13/20=65% → 10/17=59%)', () => {
    expect(progressPercent(DEF, drinkerSmokerAnswers(), 'smoking_lifetime', 'MALE')).toBe(65)
    expect(progressPercent(DEF, { ...drinkerSmokerAnswers(), alcohol_ever: 1 }, 'smoking_lifetime', 'MALE')).toBe(59)
  })

  it('보일 문항이 없으면 100%', () => {
    const def: SurveyDefinition = {
      survey_version: 't',
      kind: 'ONBOARDING',
      questions: [{ no: 1, field: 'p', text: 'P', type: 'BOOLEAN', only_for: 'FEMALE' }],
    }
    expect(progressPercent(def, {}, 'p', 'MALE')).toBe(100)
  })
})
