// frontend/src/records/records.test.ts
// 기록 탭 규칙: 항목 주소·값 문구·입력칸 숫자 읽기, 그래프 좌표, 서울 시각

import { describe, expect, it } from 'vitest'
import { DEFAULT_RECORD_KIND, formatLogValue, parseFieldValue, RECORD_TYPES, recordTypeOf } from './recordTypes'
import { chartLines, dayPosition, logTimeLabel, nowInSeoulInput } from './recordView'

describe('recordTypes', () => {
  it('탭 순서는 Figma M07 (혈압·혈당·체중·걸음·운동·음주), 기본은 혈압', () => {
    expect(RECORD_TYPES.map((type) => type.tab)).toEqual(['혈압', '혈당', '체중', '걸음', '운동', '음주'])
    expect(DEFAULT_RECORD_KIND).toBe('blood-pressure')
    expect(recordTypeOf('meals')).toBeUndefined() // 식단은 MealsPage
  })

  it('혈압만 두 칸, 체중·음주만 소수 (api.md 6-0)', () => {
    expect(RECORD_TYPES.filter((type) => type.fields.length === 2).map((type) => type.logType)).toEqual(['BLOOD_PRESSURE'])
    const decimals = RECORD_TYPES.filter((type) => type.fields.some((field) => field.decimal)).map((type) => type.logType)
    expect(decimals).toEqual(['WEIGHT', 'ALCOHOL'])
  })

  it('값 문구', () => {
    expect(formatLogValue(recordTypeOf('blood-pressure')!, 132, 84)).toBe('132/84 mmHg')
    expect(formatLogValue(recordTypeOf('weight')!, 68.5, null)).toBe('68.5 kg')
  })

  it('입력칸 읽기: 빈칸·글자는 null, 공백은 무시', () => {
    expect(parseFieldValue(' 128 ')).toBe(128)
    expect(parseFieldValue('68.5')).toBe(68.5)
    expect(parseFieldValue('')).toBeNull()
    expect(parseFieldValue('abc')).toBeNull()
  })
})

describe('chartLines', () => {
  it('두 줄을 같은 눈금으로 (큰 값이 위), x는 날짜 위치', () => {
    const [systolic, diastolic] = chartLines(
      [
        [{ x: 0, y: 140 }, { x: 1, y: 120 }],
        [{ x: 0, y: 90 }, { x: 1, y: 80 }],
      ],
      100,
      100,
      0,
    )
    expect(systolic).toBe('0,0 100,33.3')
    expect(diastolic).toBe('0,83.3 100,100')
  })

  it('같은 값이면 가운데 높이, 기록이 없으면 빈 줄', () => {
    expect(chartLines([[{ x: 0.5, y: 70 }]], 100, 60, 0)).toEqual(['50,30'])
    expect(chartLines([[]], 100, 60)).toEqual([''])
  })
})

describe('dayPosition (빠진 날은 간격이 벌어짐, #139 리뷰)', () => {
  it('시작일 0, 13일째 1, 그 사이는 비율', () => {
    expect(dayPosition('2026-11-13', '2026-11-13')).toBe(0)
    expect(dayPosition('2026-11-26', '2026-11-13')).toBe(1)
    expect(dayPosition('2026-11-19', '2026-11-13')).toBeCloseTo(6 / 13)
  })
})

describe('서울 시각', () => {
  it('목록 시각: UTC 밤이어도 서울 날짜', () => {
    expect(logTimeLabel('2026-11-18T22:40:00Z')).toBe('11월 19일 07:40')
  })

  it('입력칸 기본값은 서울 지금 (datetime-local 형식)', () => {
    expect(nowInSeoulInput(new Date('2026-11-18T22:40:00Z'))).toBe('2026-11-19T07:40')
  })
})
