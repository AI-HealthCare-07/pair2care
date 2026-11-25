// frontend/src/survey/testFixtures.ts
// 설문 테스트(survey.test.ts·navigation.test.ts)에서 같이 쓰는 답 묶음. 화면 코드에서는 쓰지 않음.

import type { SurveyAnswers } from './types'

/** 술·담배 모두 하는 남성: 건너뛰기 없이 20문항(21번 임신 제외)이 모두 보임 */
export function drinkerSmokerAnswers(): SurveyAnswers {
  return {
    height_cm: 172.5,
    weight_kg: 78.2,
    waist_cm: 88,
    father_diabetes_history: 1,
    mother_diabetes_history: 0,
    sibling_diabetes_history: 8, // 사용자가 고른 "형제자매 없음"
    father_hypertension_history: 9,
    mother_hypertension_history: 0,
    sibling_hypertension_history: 0,
    alcohol_ever: 2,
    alcohol_frequency: 4,
    alcohol_amount: 2,
    binge_frequency: 2,
    smoking_lifetime: 2,
    smoking_current: 1,
    cigarettes_per_day: 10,
    heated_tobacco: 8, // 사용자가 고른 "사용한 적 없음"
    liquid_ecig: 8,
    is_hypertension_diagnosed: false,
    is_diabetes_diagnosed: false,
  }
}
