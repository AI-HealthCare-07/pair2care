// frontend/src/api/healthProfiles.mock.ts
// 3-1 저장 구현 전에 설문 화면을 만들 때 쓰는 가짜 API (healthProfiles.ts와 함수 이름·시그니처가 같음).
// 응답 모양은 api.md 3-1 예시와 같고, 예측 점수는 고정값(가짜). 진단 "예"·임신 규칙은 서버 규칙을 흉내 냄.

import { ApiError } from './client'
import type { CreateHealthProfileResponse, Disease, Prediction } from './healthProfiles'
import { SURVEY_DEFINITION_ONBOARDING } from '../survey/definition'
import type { HealthProfileRequest, SurveyDefinition, SurveyKind } from '../survey/types'

const wait = (ms = 250) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T

let nextError: ApiError | null = null

/** 다음 저장 요청 한 번만 이 에러로 실패시킴 (409·400 처리 화면 확인용). null이면 해제 */
export function setMockSurveyError(err: ApiError | null) {
  nextError = err
}

// 재설문에서 묻는 문항(survey-mapping.md "재설문: 물음")과 13·16번 ask_when_applicable 예시
const WEEKLY_ASKED = new Set([2, 3, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21])

export async function getSurveyDefinition(kind: SurveyKind): Promise<SurveyDefinition> {
  await wait()
  const base = clone(SURVEY_DEFINITION_ONBOARDING)
  if (kind === 'ONBOARDING') return base
  return {
    ...base,
    kind: 'WEEKLY',
    questions: base.questions
      .filter((q) => WEEKLY_ASKED.has(q.no))
      .map((q) => (q.no === 13 || q.no === 16 ? { ...q, ask_when_applicable: true } : q)),
  }
}

export async function postHealthProfile(body: HealthProfileRequest): Promise<CreateHealthProfileResponse> {
  await wait()
  if (nextError) {
    const err = nextError
    nextError = null
    throw err
  }
  if (body.survey_version !== SURVEY_DEFINITION_ONBOARDING.survey_version) {
    throw new ApiError(409, '설문 문항이 바뀌었어요. 다시 불러올게요.', 'SURVEY_VERSION_MISMATCH')
  }

  // 서버가 채우는 값(건너뛰기 코드)을 흉내: alcohol → 8, smoking → 8 / 888
  const profile = { ...body }
  if (body.alcohol_ever === 1) {
    profile.alcohol_frequency = 8
    profile.alcohol_amount = 8
    profile.binge_frequency = 8
  } else if (body.alcohol_frequency === 1) {
    profile.alcohol_amount = 8
    profile.binge_frequency = 8
  }
  if (body.smoking_lifetime === 3) {
    profile.smoking_current = 8
    profile.cigarettes_per_day = 888
  } else if (body.smoking_current === 3) {
    profile.cigarettes_per_day = 888
  }

  const managed: Disease[] = []
  if (body.is_hypertension_diagnosed === true) managed.push('HYPERTENSION')
  if (body.is_diabetes_diagnosed === true) managed.push('DIABETES')
  const pregnant = body.is_pregnant === true

  const all: Prediction[] = [
    { id: 51, disease: 'DIABETES', method: 'MODEL', score: 34, level: 'CAUTION' },
    { id: 52, disease: 'HYPERTENSION', method: 'MODEL', score: 21, level: 'LOW' },
  ]
  return {
    health_profile: { ...profile, id: 31, created_at: new Date().toISOString() },
    predictions: pregnant ? [] : all.filter((p) => !managed.includes(p.disease)),
    managed_diseases: managed,
    skipped_reason: pregnant ? 'PREGNANT' : null,
    prediction_error: false,
  }
}
