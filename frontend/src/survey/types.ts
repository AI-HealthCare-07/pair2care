// frontend/src/survey/types.ts
// 설문 문항 정의(api.md 3-6)와 3-1 저장 요청의 타입. 서버가 내려주는 JSON 모양 그대로(snake_case).

export type SurveyKind = 'ONBOARDING' | 'WEEKLY'
export type Gender = 'MALE' | 'FEMALE' // users.gender (2-1 가입 응답·2-5 내 정보의 gender와 같은 값)
export type AnswerValue = number | boolean

export interface QuestionOption {
  label: string
  value: AnswerValue
}

/** 이 문항의 값이 when이면 fields 문항은 화면에서 건너뛰고 null로 보냄 */
export interface SkipRule {
  when: AnswerValue
  fields: string[]
}

export interface Question {
  no: number
  field: string // 3-1 요청 필드 이름과 같은 영문 (400 SURVEY_FIELD_INVALID의 field와도 같음)
  text: string // 기본 문구
  text_by_gender?: Partial<Record<Gender, string>> // 있으면 성별에 맞는 문구를 text 대신 사용
  help?: string | null // 질문 아래 보조 설명 (Figma M02, api.md 3-6 공통 필드·선택). 없으면 생략되거나 null이라 안 보여 줌
  type: 'SINGLE' | 'NUMBER' | 'BOOLEAN'
  options?: QuestionOption[] // SINGLE·BOOLEAN. 배열 순서 = 화면 순서
  min?: number // NUMBER
  max?: number
  step?: number
  unit?: string
  required?: boolean // NUMBER만 명시. SINGLE·BOOLEAN은 화면에 보이면 필수
  only_for?: Gender // 이 성별에게만 물음 (예: 임신)
  skip?: SkipRule[]
  ask_when_applicable?: boolean // kind=WEEKLY의 13·16번만. false면 해당돼도 묻지 않음(서버가 직전 값 복사)
}

export interface SurveyDefinition {
  survey_version: string // 'v1.0'. 3-1 요청에 그대로 보냄 (다르면 409)
  kind: SurveyKind
  questions: Question[]
}

/** 화면에서 모은 답. 아직 안 고른 문항은 키가 없거나 undefined, 건너뛰기 가능한 문항은 null */
export type SurveyAnswers = Record<string, AnswerValue | null | undefined>

/** 3-1 요청 본문. 문항 필드는 정의에 따라 달라서 index signature로 둠 */
export interface HealthProfileRequest {
  kind: SurveyKind
  survey_version: string
  [field: string]: AnswerValue | null | string
}
