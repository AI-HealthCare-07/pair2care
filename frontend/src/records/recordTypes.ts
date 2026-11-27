// frontend/src/records/recordTypes.ts
// 기록 탭(S-19, Figma M07)의 항목 7개: 주소 조각(kind) ↔ 서버 log_type ↔ 화면 문구·입력칸
// 값 범위·소수점 검사는 서버가 함 (api.md 6-0, 400 문구를 그대로 보여 줌) → 여기선 입력칸 모양만 정함

import type { DailyLogType } from '../api/healthLogs'
import type { Disease } from '../api/predictions'

export interface RecordField {
  key: 'value' | 'value2'
  label: string // "수축기 혈압 (mmHg)"
  placeholder: string // "예: 128"
  decimal: boolean // 소수 첫째 자리까지 받는 항목 (체중·음주, api.md 6-0)
}

export interface RecordType {
  kind: string // 주소: /records/<kind>
  logType: DailyLogType
  tab: string // 탭 이름
  title: string // 카드·입력 화면 제목에 쓰는 이름 ("혈압")
  unit: string // 목록에 붙이는 단위
  fields: RecordField[]
  hint?: string // 입력 화면 제목 아래 안내
  trendDisease?: Disease // 이 탭 아래 위험도 추이 카드 (혈압 → 고혈압, 혈당 → 당뇨)
}

const num = (key: RecordField['key'], label: string, placeholder: string, decimal = false): RecordField => ({
  key,
  label,
  placeholder,
  decimal,
})

// 탭 순서 = Figma M07 (혈압·혈당·체중·걸음·운동·음주·식단). 식단은 현지 님 MealsPage(/records/meals)라 여기 없음
export const RECORD_TYPES: RecordType[] = [
  {
    kind: 'blood-pressure',
    logType: 'BLOOD_PRESSURE',
    tab: '혈압',
    title: '혈압',
    unit: 'mmHg',
    fields: [num('value', '수축기 혈압 (mmHg)', '예: 128'), num('value2', '이완기 혈압 (mmHg)', '예: 82')],
    hint: '집에서 잰 값만 그래프에 보여요. 검진 수치와 섞지 않아요.',
    trendDisease: 'HYPERTENSION',
  },
  {
    kind: 'blood-glucose',
    logType: 'BLOOD_GLUCOSE',
    tab: '혈당',
    title: '혈당',
    unit: 'mg/dL',
    fields: [num('value', '혈당 (mg/dL)', '예: 105')],
    trendDisease: 'DIABETES',
  },
  { kind: 'weight', logType: 'WEIGHT', tab: '체중', title: '체중', unit: 'kg', fields: [num('value', '체중 (kg)', '예: 68.5', true)] },
  {
    kind: 'steps',
    logType: 'STEPS',
    tab: '걸음',
    title: '걸음 수',
    unit: '보',
    fields: [num('value', '걸음 수 (보)', '예: 6000')],
    hint: '하루에 한 번 기록해요. 같은 날 다시 넣으면 그날 값이 바뀌어요.',
  },
  {
    kind: 'exercise',
    logType: 'EXERCISE',
    tab: '운동',
    title: '운동',
    unit: '분',
    fields: [num('value', '운동 시간 (분)', '예: 30')],
  },
  {
    kind: 'alcohol',
    logType: 'ALCOHOL',
    tab: '음주',
    title: '음주',
    unit: '잔',
    fields: [num('value', '마신 잔 수 (잔)', '예: 2', true)],
    hint: '소주잔이나 맥주잔으로 세어 주세요. 안 마신 날은 0으로 넣어도 돼요.',
  },
]

export const DEFAULT_RECORD_KIND = RECORD_TYPES[0].kind
export const MEALS_TAB = { kind: 'meals', tab: '식단', path: '/records/meals' } as const

export function recordTypeOf(kind: string | undefined): RecordType | undefined {
  return RECORD_TYPES.find((type) => type.kind === kind)
}

/** 목록에 보이는 값: 혈압은 "132/84 mmHg", 나머지는 "68.5 kg" */
export function formatLogValue(type: RecordType, value: number, value2: number | null): string {
  const main = value2 === null ? `${value}` : `${value}/${value2}`
  return `${main} ${type.unit}`
}

/** 입력칸 글자 → 서버로 보낼 숫자. 빈칸·숫자가 아니면 null (화면이 "입력해 주세요" 표시) */
export function parseFieldValue(text: string): number | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  return Number.isFinite(value) ? value : null
}
