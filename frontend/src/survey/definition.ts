// frontend/src/survey/definition.ts
// 가입 설문(ONBOARDING) 21문항. api.md 3-6과 같은 JSON 모양의 프론트 상수.
// ⚠️ 임시: 서버 상수가 기준이고, S-11 구현 전에 GET /health-profiles/questions(3-6)로 바꿈.
//    문구·보기는 docs/survey-mapping.md 기준. 실제 문구는 서버(장성은)가 확정하면 그걸 따름.
//    survey_version은 서버 값과 글자까지 같아야 함 (다르면 409 SURVEY_VERSION_MISMATCH).

import type { Question, QuestionOption, SurveyDefinition } from './types'

const YES_NO_UNKNOWN: QuestionOption[] = [
  { label: '예', value: 1 },
  { label: '아니요', value: 0 }, // #86에서 대응표·서버 상수가 '아니요'로 통일됨
  { label: '모름', value: 9 },
]
const YES_NO_UNKNOWN_NO_SIBLING: QuestionOption[] = [...YES_NO_UNKNOWN, { label: '형제자매 없음', value: 8 }]
const YES_NO: QuestionOption[] = [
  { label: '예', value: true },
  { label: '아니요', value: false },
]

const questions: Question[] = [
  { no: 1, field: 'height_cm', text: '키를 알려 주세요.', type: 'NUMBER', min: 100.0, max: 230.0, step: 0.1, unit: 'cm', required: true },
  { no: 2, field: 'weight_kg', text: '몸무게를 알려 주세요.', type: 'NUMBER', min: 25.0, max: 300.0, step: 0.1, unit: 'kg', required: true },
  { no: 3, field: 'waist_cm', text: '허리둘레를 알려 주세요.', type: 'NUMBER', min: 40.0, max: 200.0, step: 0.1, unit: 'cm', required: false },

  { no: 4, field: 'father_diabetes_history', text: '아버지가 당뇨 진단을 받았나요?', type: 'SINGLE', options: YES_NO_UNKNOWN },
  { no: 5, field: 'mother_diabetes_history', text: '어머니가 당뇨 진단을 받았나요?', type: 'SINGLE', options: YES_NO_UNKNOWN },
  { no: 6, field: 'sibling_diabetes_history', text: '형제자매 중 당뇨 진단을 받은 사람이 있나요?', type: 'SINGLE', options: YES_NO_UNKNOWN_NO_SIBLING },
  { no: 7, field: 'father_hypertension_history', text: '아버지가 고혈압 진단을 받았나요?', type: 'SINGLE', options: YES_NO_UNKNOWN },
  { no: 8, field: 'mother_hypertension_history', text: '어머니가 고혈압 진단을 받았나요?', type: 'SINGLE', options: YES_NO_UNKNOWN },
  { no: 9, field: 'sibling_hypertension_history', text: '형제자매 중 고혈압 진단을 받은 사람이 있나요?', type: 'SINGLE', options: YES_NO_UNKNOWN_NO_SIBLING },

  {
    no: 10, field: 'alcohol_ever', text: '지금까지 술을 마셔 본 적이 있나요?', type: 'SINGLE',
    options: [{ label: '없다', value: 1 }, { label: '있다', value: 2 }],
    skip: [{ when: 1, fields: ['alcohol_frequency', 'alcohol_amount', 'binge_frequency'] }],
  },
  {
    no: 11, field: 'alcohol_frequency', text: '최근 1년간 술을 얼마나 자주 마셨나요?', type: 'SINGLE',
    options: [
      { label: '전혀 마시지 않았다', value: 1 },
      { label: '월 1회 미만', value: 2 },
      { label: '월 1회 정도', value: 3 },
      { label: '월 2~4회', value: 4 },
      { label: '주 2~3회', value: 5 },
      { label: '주 4회 이상', value: 6 },
    ],
    skip: [{ when: 1, fields: ['alcohol_amount', 'binge_frequency'] }],
  },
  {
    no: 12, field: 'alcohol_amount', text: '술 마시는 날 한 번에 몇 잔 정도 마시나요?', type: 'SINGLE',
    help: '술 종류 상관없이 마신 잔 수로 골라 주세요 (캔맥주 1개는 1.6잔)', // 장성은(국건영 조사표 기준 캔맥주 환산) 확정 문구
    options: [
      { label: '1~2잔', value: 1 },
      { label: '3~4잔', value: 2 },
      { label: '5~6잔', value: 3 },
      { label: '7~9잔', value: 4 },
      { label: '10잔 이상', value: 5 },
    ],
  },
  {
    no: 13, field: 'binge_frequency',
    text: '한 번의 술자리에서 남자 소주 7잔(맥주 5캔)·여자 5잔(맥주 3캔) 이상 마시는 날이 얼마나 있나요?',
    text_by_gender: {
      MALE: '한 번의 술자리에서 소주 7잔(맥주 5캔) 이상 마시는 날이 얼마나 있나요?',
      FEMALE: '한 번의 술자리에서 소주 5잔(맥주 3캔) 이상 마시는 날이 얼마나 있나요?',
    },
    type: 'SINGLE',
    options: [
      { label: '전혀 없음', value: 1 },
      { label: '월 1회 미만', value: 2 },
      { label: '월 1회 정도', value: 3 },
      { label: '주 1회 정도', value: 4 },
      { label: '거의 매일', value: 5 },
    ],
  },

  {
    no: 14, field: 'smoking_lifetime', text: '지금까지 담배(궐련)를 얼마나 피웠나요?', type: 'SINGLE',
    // 화면 순서와 저장값이 다름: 피운 적 없음 3 / 5갑 미만 1 / 5갑 이상 2
    options: [
      { label: '피운 적 없음', value: 3 },
      { label: '5갑(100개비) 미만', value: 1 },
      { label: '5갑(100개비) 이상', value: 2 },
    ],
    skip: [{ when: 3, fields: ['smoking_current', 'cigarettes_per_day'] }],
  },
  {
    no: 15, field: 'smoking_current', text: '지금 담배(궐련)를 피우나요?', type: 'SINGLE',
    options: [
      { label: '매일', value: 1 },
      { label: '가끔', value: 2 },
      { label: '과거엔 피웠으나 지금은 안 피움', value: 3 },
    ],
    skip: [{ when: 3, fields: ['cigarettes_per_day'] }],
  },
  { no: 16, field: 'cigarettes_per_day', text: '하루 평균 몇 개비 피우나요?', type: 'NUMBER', min: 1, max: 60, step: 1, unit: '개비', required: true },

  {
    no: 17, field: 'heated_tobacco', text: '궐련형 전자담배를 사용하나요?', type: 'SINGLE',
    options: [
      { label: '사용한 적 없음', value: 8 },
      { label: '매일', value: 1 },
      { label: '가끔', value: 2 },
      { label: '과거엔 썼으나 지금은 안 씀', value: 3 },
    ],
  },
  {
    no: 18, field: 'liquid_ecig', text: '액상형 전자담배를 사용하나요?', type: 'SINGLE',
    options: [
      { label: '사용한 적 없음', value: 8 },
      { label: '지금 사용함', value: 1 },
      { label: '지금은 안 씀', value: 2 },
    ],
  },

  { no: 19, field: 'is_hypertension_diagnosed', text: '고혈압 진단을 받은 적 있나요?', type: 'BOOLEAN', options: YES_NO },
  { no: 20, field: 'is_diabetes_diagnosed', text: '당뇨 진단을 받은 적 있나요?', type: 'BOOLEAN', options: YES_NO },
  { no: 21, field: 'is_pregnant', text: '지금 임신 중인가요?', type: 'BOOLEAN', options: YES_NO, only_for: 'FEMALE' },
]

export const SURVEY_DEFINITION_ONBOARDING: SurveyDefinition = {
  survey_version: 'v1.0',
  kind: 'ONBOARDING',
  questions,
}
