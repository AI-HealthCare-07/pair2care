import { describe, expect, it } from 'vitest'
import { BLOOD_PRESSURE_DETAIL, FUTURE_DATE_DETAIL, MISSING_DATE_DETAIL, NO_VALUE_DETAIL, checkCheckup } from './checkupFields'

const TODAY = '2026-11-27'

describe('checkCheckup (S-07, api.md 4-1)', () => {
  it('숫자로 바꿔서 빈칸은 빼고 보냄', () => {
    expect(checkCheckup('2026-05-10', { systolic_bp: '134', diastolic_bp: ' 86 ', waist_cm: '91.5', hba1c: '' }, TODAY)).toEqual({
      ok: true,
      checkedOn: '2026-05-10',
      values: { systolic_bp: 134, diastolic_bp: 86, waist_cm: 91.5 },
    })
  })

  it('오늘은 되고 내일은 안 됨, 날짜가 비면 안 됨', () => {
    expect(checkCheckup(TODAY, { fasting_glucose: '102' }, TODAY).ok).toBe(true)
    expect(checkCheckup('2026-11-28', { fasting_glucose: '102' }, TODAY)).toEqual({ ok: false, field: 'checked_on', message: FUTURE_DATE_DETAIL })
    expect(checkCheckup('', { fasting_glucose: '102' }, TODAY)).toEqual({ ok: false, field: 'checked_on', message: MISSING_DATE_DETAIL })
  })

  it.each([
    ['systolic_bp', '59'],
    ['systolic_bp', '261'],
    ['fasting_glucose', '601'],
    ['waist_cm', '39.9'],
    ['triglyceride', '2001'],
    ['hdl_cholesterol', '9'],
    ['hba1c', '15.1'],
  ] as const)('%s=%s 범위 밖은 그 칸 오류', (key, text) => {
    const result = checkCheckup(TODAY, { [key]: text }, TODAY)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.field).toBe(key)
  })

  it('범위 양 끝은 통과', () => {
    expect(checkCheckup(TODAY, { systolic_bp: '260', diastolic_bp: '30', waist_cm: '200.0', hba1c: '3.0' }, TODAY).ok).toBe(true)
  })

  it('정수 칸에 소수점, 소수 칸에 둘째 자리, 숫자 아닌 글자는 막음', () => {
    expect(checkCheckup(TODAY, { fasting_glucose: '102.5' }, TODAY)).toMatchObject({ ok: false, field: 'fasting_glucose' })
    expect(checkCheckup(TODAY, { waist_cm: '88.25' }, TODAY)).toMatchObject({ ok: false, field: 'waist_cm' })
    expect(checkCheckup(TODAY, { hba1c: '5,6' }, TODAY)).toMatchObject({ ok: false, field: 'hba1c' })
  })

  it('수축기가 이완기보다 크지 않으면 서버와 같은 문구', () => {
    expect(checkCheckup(TODAY, { systolic_bp: '80', diastolic_bp: '80' }, TODAY)).toEqual({ ok: false, field: 'systolic_bp', message: BLOOD_PRESSURE_DETAIL })
  })

  it('하나도 없으면 칸이 아닌 화면 오류', () => {
    expect(checkCheckup(TODAY, { systolic_bp: '  ' }, TODAY)).toEqual({ ok: false, field: null, message: NO_VALUE_DETAIL })
  })

  it('날짜 → 혈압 → 최소 1개 순서로 첫 오류 하나만', () => {
    expect(checkCheckup('2026-12-01', {}, TODAY)).toMatchObject({ field: 'checked_on' })
  })
})
