// frontend/src/prediction/labels.ts
// S-09 화면 문구 상수. 서버는 코드값만 주고 문구는 프론트가 정함 (api.md 5-3 "feature → 화면 문구는 프론트 상수").
// 확정: LOW 한 줄(성은 님), 요인 14개·ℹ️ 나이 안내(#107 성은 님), 범위 밖 건강 나이(#102 "30세 미만 / 69세 초과")

import type { Disease, Factor, RiskLevel } from '../api/predictions'

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
 * LOW는 확정 (정답이 "전단계 이상"이라 LOW에도 실제 위험한 분이 섞여 있어서 "상대적으로 낮은 편", 성은 님 11/25).
 * TODO(성은 님 문구 확인): CAUTION·HIGH는 임시 문구
 */
export const LEVEL_MESSAGE: Record<RiskLevel, string> = {
  LOW: '상대적으로 낮은 편이에요. 지금처럼 유지해도 좋아요',
  CAUTION: '생활습관을 조금씩 바꿔 보면 좋아요',
  HIGH: '보건소나 병원에서 한 번 확인해 보길 권해요',
}

/** 영향을 준 요인 카드 맨 아래 ℹ️ 안내 (#107, 요인 후보에서 나이를 뺀 이유) */
export const AGE_IN_SCORE_NOTICE = '점수에는 나이도 반영돼요. 나이는 바꿀 수 없어서 요인에서는 뺐어요'

/** 관리 중 카드 (진단 "예" → 예측 안 함, api.md 5-0 managed_diseases) */
export const MANAGED_TITLE = '관리 중'
export const MANAGED_MESSAGE = '진단받은 질환은 위험도를 계산하지 않아요. 지금처럼 진료를 이어 가세요'

/** 질환 하나만 계산이 안 됐을 때 그 카드에 보이는 문구 */
export const MISSING_MESSAGE = '이번에는 위험도를 계산하지 못했어요'

/**
 * 요인 문구 14개 (#107 성은 님 초안). 질환 소제목 아래에 보여서 질환 이름은 뺌.
 * 가족력은 질환 상관없이 "누구의 가족력"만: father_diabetes_history·father_hypertension_history → 'father'
 * TODO(성은 님 답 대기): 술을 안 마시는 분도 alcohol_* DOWN이 나와서 "평균보다 적어요"가 보임 → 문구를 넓힐지
 */
const FACTOR_TEXT: Record<string, Record<Factor['direction'], string>> = {
  bmi: { UP: '체중(BMI)이 평균보다 높아요', DOWN: '체중(BMI)이 평균보다 낮아요' },
  father: { UP: '아버지 가족력이 있어요', DOWN: '아버지 가족력이 없어요' },
  mother: { UP: '어머니 가족력이 있어요', DOWN: '어머니 가족력이 없어요' },
  sibling: { UP: '형제자매 가족력이 있어요', DOWN: '형제자매 가족력이 없어요' },
  alcohol_frequency: { UP: '술 마시는 횟수가 평균보다 많아요', DOWN: '술 마시는 횟수가 평균보다 적어요' },
  alcohol_amount: { UP: '한 번에 마시는 양이 평균보다 많아요', DOWN: '한 번에 마시는 양이 평균보다 적어요' },
  smoking_current: { UP: '지금 담배를 피워요', DOWN: '지금 담배를 피우지 않아요' },
}

const FAMILY_FEATURE = /^(father|mother|sibling)_(diabetes|hypertension)_history$/

/** 요인 한 개의 문구. 모르는 feature(예: #107 전에 저장된 age, sex)는 null → 화면에서 건너뜀 */
export function factorText(factor: Factor): string | null {
  const family = FAMILY_FEATURE.exec(factor.feature)
  const key = family ? family[1] : factor.feature
  return FACTOR_TEXT[key]?.[factor.direction] ?? null
}
