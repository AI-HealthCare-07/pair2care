// frontend/src/prediction/labels.ts
// S-09 화면 문구 상수. 서버는 코드값만 주고 문구는 프론트가 정함 (api.md 5-3 "feature → 화면 문구는 프론트 상수").
// 확정: 단계별 한 줄(성은 님), 요인 14개·ℹ️ 나이 안내(#107 성은 님, 술 DOWN 문구 11/25 수정), 범위 밖 건강 나이(#102 "30세 미만 / 69세 초과")

import type { Disease, Factor, MetabolicSyndrome, RiskLevel } from '../api/predictions'

/** 화면 카드 순서: Figma M04 (고혈압 → 당뇨). 서버 응답 순서(당뇨 → 고혈압)와 다름 */
export const DISEASE_ORDER: readonly Disease[] = ['HYPERTENSION', 'DIABETES']

export const DISEASE_LABEL: Record<Disease, string> = {
  HYPERTENSION: '고혈압',
  DIABETES: '당뇨',
}

/** 단계 글자: 색만으로 구분하지 않도록 배지·게이지 라벨에 항상 같이 보여 줌 (팀장님 11/25) */
export const LEVEL_LABEL: Record<RiskLevel, string> = {
  LOW: '낮음',
  CAUTION: '주의',
  HIGH: '높음',
}

/**
 * 모델 행 카드의 단계별 한 줄.
 * LOW: 정답이 "전단계 이상"이라 LOW에도 실제 위험한 분이 섞여 있어서 "상대적으로 낮은 편" (성은 님 11/25)
 * CAUTION·HIGH: #111 리뷰에서 성은 님 확정
 */
export const LEVEL_MESSAGE: Record<RiskLevel, string> = {
  LOW: '상대적으로 낮은 편이에요. 지금처럼 유지해도 좋아요',
  CAUTION: '생활습관을 조금씩 바꿔 보면 좋아요',
  HIGH: '보건소나 병원에서 한 번 확인해 보길 권해요',
}

/** 영향을 준 요인 카드 맨 아래 ℹ️ 안내 (#107, 요인 후보에서 나이를 뺀 이유) */
export const AGE_IN_SCORE_NOTICE = '점수에는 나이도 반영돼요. 나이는 바꿀 수 없어서 요인에서는 뺐어요'

/** 요인 줄의 "+5살"이 무슨 숫자인지 (#123 성은 님 제안). 숫자가 하나라도 보일 때만 ℹ️ 맨 위에 */
export const YEARS_NOTICE = '숫자는 같은 성별 평균인 사람보다 건강 나이를 몇 살 높이거나 낮추는지예요'

/** 관리 중 카드 (진단 "예" → 예측 안 함, api.md 5-0 managed_diseases) */
export const MANAGED_TITLE = '관리 중'
export const MANAGED_MESSAGE = '진단받은 질환은 위험도를 계산하지 않아요. 지금처럼 진료를 이어 가세요'

/** 질환 하나만 계산이 안 됐을 때 그 카드에 보이는 문구 */
export const MISSING_MESSAGE = '이번에는 위험도를 계산하지 못했어요'

// 예측 실패 화면 (5-5 다시 계산)
export const FAILED_TITLE = '위험도를 계산하지 못했어요'
export const FAILED_MESSAGE = '설문은 저장됐고, 위험도 계산만 실패했어요. 아래 버튼으로 다시 계산해 볼 수 있어요.'
export const RETRY_BUTTON = '다시 계산하기'
export const RETRY_BUSY = '계산하고 있어요'
export const RETRY_FAILED_AGAIN = '지금은 계산할 수 없어요. 잠시 후 다시 시도해 주세요.'

/**
 * 요인 문구 14개 (#107 성은 님 초안, #114에서 기준이 같은 성별 평균으로 바뀌어 체중·음주 4개 수정). 질환 소제목 아래라 질환 이름은 뺌.
 * 가족력은 질환 상관없이 "누구의 가족력"만: father_diabetes_history·father_hypertension_history → 'father'
 * 술: 안 마시는 분은 빈도 1·양 0으로 들어가 둘 다 DOWN이 나올 수 있음 → DOWN은 안 마시는 분에게도 맞는 문장으로
 *     (양 DOWN은 "한 번에"를 뺌, 빈도 DOWN은 그대로도 맞음. UP은 마시는 분만 나옴, 성은 님 11/25)
 */
const FACTOR_TEXT: Record<string, Record<Factor['direction'], string>> = {
  bmi: { UP: '체중(BMI)이 같은 성별 평균보다 높아요', DOWN: '체중(BMI)이 같은 성별 평균보다 낮아요' },
  father: { UP: '아버지 가족력이 있어요', DOWN: '아버지 가족력이 없어요' },
  mother: { UP: '어머니 가족력이 있어요', DOWN: '어머니 가족력이 없어요' },
  sibling: { UP: '형제자매 가족력이 있어요', DOWN: '형제자매 가족력이 없어요' },
  alcohol_frequency: { UP: '술 마시는 횟수가 같은 성별 평균보다 많아요', DOWN: '술 마시는 횟수가 같은 성별 평균보다 적어요' },
  alcohol_amount: { UP: '한 번에 마시는 양이 같은 성별 평균보다 많아요', DOWN: '술 마시는 양이 같은 성별 평균보다 적어요' },
  smoking_current: { UP: '지금 담배를 피워요', DOWN: '지금 담배를 피우지 않아요' },
}

/** 가감 나이 표시: 5 → "+5살", -1 → "−1살"(마이너스 기호 U+2212). null·0·숫자 아님은 null → 숨김 */
export function yearsText(years: number | null | undefined): string | null {
  if (typeof years !== 'number' || !Number.isFinite(years) || years === 0) return null
  return years > 0 ? `+${years}살` : `\u2212${Math.abs(years)}살`
}

/**
 * years가 null(또는 없음)이면 서버가 예측 때 저장한 옛 기준(남녀 합친 학습 평균) 요인을 줌 (means_by_sex 없음·예전 모델 행, api.md 5-3)
 * → 체중·음주 3개만 "같은 성별" 없이 원래 문구(#107)로. 가족력·흡연은 평균과 상관없는 문장이라 그대로 (#123 현영 님)
 */
const LEGACY_AVERAGE_TEXT: Record<string, Record<Factor['direction'], string>> = {
  bmi: { UP: '체중(BMI)이 평균보다 높아요', DOWN: '체중(BMI)이 평균보다 낮아요' },
  alcohol_frequency: { UP: '술 마시는 횟수가 평균보다 많아요', DOWN: '술 마시는 횟수가 평균보다 적어요' },
  alcohol_amount: { UP: '한 번에 마시는 양이 평균보다 많아요', DOWN: '술 마시는 양이 평균보다 적어요' },
}

const FAMILY_FEATURE = /^(father|mother|sibling)_(diabetes|hypertension)_history$/

/** 요인 한 개의 문구. 모르는 feature(예: #107 전에 저장된 age, sex)는 null → 화면에서 건너뜀. years 유무로 평균 기준 문구를 고름 */
export function factorText(factor: Factor): string | null {
  const family = FAMILY_FEATURE.exec(factor.feature)
  const key = family ? family[1] : factor.feature
  const sameSexBasis = typeof factor.years === 'number'
  if (!sameSexBasis && LEGACY_AVERAGE_TEXT[key]) return LEGACY_AVERAGE_TEXT[key][factor.direction]
  return FACTOR_TEXT[key]?.[factor.direction] ?? null
}

// ───── 12/4 범위: 검진 기준표 줄 · 대사증후군 · 빠진 검진 항목 → S-07 (wireframe.md S-09, api.md 5-1) ─────

/**
 * 질환 카드 안 검진 기준표 줄 (method = CHECKUP_CRITERIA). "진단" 대신 "수치가 ○○ 범위예요" (wireframe.md S-09)
 * CAUTION = 전단계 이상, HIGH = 질환 범위 (api.md 5-1 기준표)
 */
export const CHECKUP_RANGE_TEXT: Record<Disease, Record<RiskLevel, string>> = {
  HYPERTENSION: { LOW: '혈압이 정상 범위예요', CAUTION: '혈압이 주의 범위예요', HIGH: '혈압이 고혈압 범위예요' },
  DIABETES: { LOW: '혈당이 정상 범위예요', CAUTION: '혈당이 주의 범위예요', HIGH: '혈당이 당뇨 범위예요' },
}

/** 기준표 CAUTION·HIGH일 때 병원 확인 권유 (wireframe.md S-09). 모델 HIGH 한 줄과 같은 문장 (#157 성은 님) */
export const CHECKUP_ADVICE = '보건소나 병원에서 한 번 확인해 보길 권해요'

/**
 * 모델은 LOW인데 검진 기준표가 CAUTION·HIGH일 때 단계 한 줄. "지금처럼 유지해도 좋아요"가
 * 바로 아래 병원 권유와 부딪혀서 앞부분만 (#157 성은 님)
 */
export const LOW_MESSAGE_WITH_CHECKUP = '상대적으로 낮은 편이에요'

/** 기준표 줄 머리. 날짜를 못 불러오면(5-3 실패) 날짜 없이 */
export function checkupHeading(checkedOn: string | null): string {
  return checkedOn ? `검진 수치(${checkedOn.replaceAll('-', '.')}) 기준` : '검진 수치 기준'
}

/** 질환 카드의 S-07 링크 문구. NONE = 유효한 검진 없음, MORE = 검진은 있는데 이 질환 항목이 빠짐 */
export const CHECKUP_PROMPT_TEXT = {
  NONE: '검진 수치를 넣으면 수치로도 확인할 수 있어요',
  MORE: '검진 수치를 더 입력하면 알 수 있어요',
} as const

/** 설문만으로는 알 수 없는 것 (REQ-PRED-002, wireframe.md S-09). 요인 카드 아래 ℹ️ */
export const SURVEY_LIMIT_NOTICE = '위험도는 설문 답으로 계산해요. 실제 혈압·혈당 수치는 설문만으로는 알 수 없어요'

export type MetabolicStatus = MetabolicSyndrome['status']

export const METABOLIC_TITLE = '대사증후군'

/** 배지 글자 (wireframe.md: 해당 / 해당 아님 / 판단 어려움) */
export const METABOLIC_BADGE: Record<MetabolicStatus, string> = {
  MET: '해당',
  NOT_MET: '해당 아님',
  UNKNOWN: '판단 어려움',
}

/** 대사증후군 기준 이름 → 화면 이름 (서버 criteria.py의 missing 값: 기준 이름이라 입력칸 이름과 다름) */
export const METABOLIC_CRITERION_LABEL: Record<string, string> = {
  waist: '허리둘레',
  triglyceride: '중성지방',
  hdl_cholesterol: 'HDL',
  blood_pressure: '혈압',
  fasting_glucose: '공복혈당',
}

export const METABOLIC_INFO = '허리둘레·중성지방·HDL·혈압·공복혈당 5개 기준 중 3개 이상이면 해당돼요'

/** 받침 있으면 "을", 없으면 "를". 한글이 아니면(HDL) "을" */
function objectParticle(word: string): string {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return '을'
  return code % 28 === 0 ? '를' : '을'
}

/** 대사증후군 카드 문구 (Figma M04 "5개 기준 중 2개 해당. 중성지방·HDL을 넣으면 알 수 있어요") */
export function metabolicMessage(status: MetabolicStatus, metCount: number, missingLabels: string[]): string {
  const count = `5개 기준 중 ${metCount}개 해당`
  if (status === 'MET') return `${count}. ${CHECKUP_ADVICE}`
  if (status === 'NOT_MET' || missingLabels.length === 0) return count
  const names = missingLabels.join('·')
  return `${count}. ${names}${objectParticle(names)} 넣으면 알 수 있어요`
}
