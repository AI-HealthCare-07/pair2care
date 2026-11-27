// frontend/src/checkup/checkupFields.ts
// S-07 검진 수치 입력 칸과 보내기 전 검사 (api.md 4-1)
//  - 범위를 벗어나면 서버는 422(배열 detail)를 줘서 칸별 문구를 못 보여 줌 → 범위는 여기서 먼저 막음
//  - 날짜·혈압 순서·최소 1개는 서버 400과 같은 문구, 같은 순서(날짜 → 혈압 → 최소 1개)

export type CheckupKey =
  | 'systolic_bp'
  | 'diastolic_bp'
  | 'fasting_glucose'
  | 'waist_cm'
  | 'triglyceride'
  | 'hdl_cholesterol'
  | 'hba1c'

export interface CheckupField {
  key: CheckupKey
  label: string
  unit: string
  placeholder: string
  min: number
  max: number
  decimal: boolean // 소수 첫째 자리까지 (허리둘레·당화혈색소)
  more: boolean // "더 입력하기"를 펼쳐야 보이는 칸
}

export const CHECKUP_FIELDS: CheckupField[] = [
  { key: 'systolic_bp', label: '수축기 혈압', unit: 'mmHg', placeholder: '예: 128', min: 60, max: 260, decimal: false, more: false },
  { key: 'diastolic_bp', label: '이완기 혈압', unit: 'mmHg', placeholder: '예: 82', min: 30, max: 160, decimal: false, more: false },
  { key: 'fasting_glucose', label: '공복혈당', unit: 'mg/dL', placeholder: '예: 102', min: 40, max: 600, decimal: false, more: false },
  { key: 'waist_cm', label: '허리둘레', unit: 'cm', placeholder: '예: 88', min: 40, max: 200, decimal: true, more: false },
  { key: 'triglyceride', label: '중성지방', unit: 'mg/dL', placeholder: '예: 150', min: 20, max: 2000, decimal: false, more: true },
  { key: 'hdl_cholesterol', label: 'HDL 콜레스테롤', unit: 'mg/dL', placeholder: '예: 50', min: 10, max: 150, decimal: false, more: true },
  { key: 'hba1c', label: '당화혈색소', unit: '%', placeholder: '예: 5.6', min: 3, max: 15, decimal: true, more: true },
]

export function isCheckupKey(value: string | null): value is CheckupKey {
  return CHECKUP_FIELDS.some((field) => field.key === value)
}

export const FUTURE_DATE_DETAIL = '검진 날짜는 오늘 이후로 입력할 수 없어요.'
export const MISSING_DATE_DETAIL = '검진 날짜를 입력해 주세요.'
export const BLOOD_PRESSURE_DETAIL = '수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요.'
export const NO_VALUE_DETAIL = '검진 수치를 하나 이상 입력해 주세요.'

export type CheckupValues = Partial<Record<CheckupKey, number>>

export type CheckupCheck =
  | { ok: true; checkedOn: string; values: CheckupValues }
  | { ok: false; field: CheckupKey | 'checked_on' | null; message: string } // field null = 칸 하나가 아닌 오류(최소 1개)

/** 한 칸 글자 → 숫자. 빈칸은 undefined, 틀리면 문구 */
function parseField(field: CheckupField, text: string): number | undefined | string {
  const trimmed = text.trim()
  if (trimmed === '') return undefined
  const pattern = field.decimal ? /^\d+(\.\d)?$/ : /^\d+$/
  if (!pattern.test(trimmed)) return field.decimal ? '숫자로, 소수점은 한 자리까지 입력해 주세요.' : '숫자로, 소수점 없이 입력해 주세요.'
  const value = Number(trimmed)
  if (value < field.min || value > field.max) return `${field.min}~${field.max} ${field.unit} 사이로 입력해 주세요.`
  return value
}

/** 보내기 전 검사. 첫 오류 하나만 돌려줌 (서버와 같은 방식) */
export function checkCheckup(checkedOn: string, texts: Partial<Record<CheckupKey, string>>, today: string): CheckupCheck {
  if (!checkedOn) return { ok: false, field: 'checked_on', message: MISSING_DATE_DETAIL }
  if (checkedOn > today) return { ok: false, field: 'checked_on', message: FUTURE_DATE_DETAIL } // YYYY-MM-DD는 글자 비교 = 날짜 비교

  const values: CheckupValues = {}
  for (const field of CHECKUP_FIELDS) {
    const parsed = parseField(field, texts[field.key] ?? '')
    if (typeof parsed === 'string') return { ok: false, field: field.key, message: parsed }
    if (parsed !== undefined) values[field.key] = parsed
  }

  const { systolic_bp: systolic, diastolic_bp: diastolic } = values
  if (systolic !== undefined && diastolic !== undefined && systolic <= diastolic) {
    return { ok: false, field: 'systolic_bp', message: BLOOD_PRESSURE_DETAIL }
  }
  if (Object.keys(values).length === 0) return { ok: false, field: null, message: NO_VALUE_DETAIL }
  return { ok: true, checkedOn, values }
}
