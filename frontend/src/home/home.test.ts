// frontend/src/home/home.test.ts
// 홈(S-12) 화면 규칙: 건강 나이 높은 쪽 하나 고르기, 날짜 문구, 출처 번호

import { describe, expect, it } from 'vitest'
import type { LatestPrediction, LatestPredictionsResponse } from '../api/predictions'
import { homeDateLabel, pickHomeHealthAge, usedSources } from './homeView'

function row(overrides: Partial<LatestPrediction>): LatestPrediction {
  return {
    id: 1,
    disease: 'DIABETES',
    method: 'MODEL',
    score: 30,
    level: 'CAUTION',
    health_age: { decade: 40, actual_age: 45, out_of_range: null },
    created_at: '2026-11-25T10:00:00+09:00',
    ...overrides,
  }
}

function latest(predictions: LatestPrediction[]): LatestPredictionsResponse {
  return { health_profile_id: 1, predictions, managed_diseases: [], skipped_reason: null, metabolic_syndrome: null }
}

describe('pickHomeHealthAge (높은 쪽 하나)', () => {
  it('단계가 높은 질환이 먼저 (점수가 낮아도)', () => {
    const picked = pickHomeHealthAge(
      latest([
        row({ disease: 'DIABETES', level: 'CAUTION', score: 59 }),
        row({ id: 2, disease: 'HYPERTENSION', level: 'HIGH', score: 60, health_age: { decade: 50, actual_age: 45, out_of_range: null } }),
      ]),
    )
    expect(picked?.disease).toBe('HYPERTENSION')
    expect(picked?.line.level).toBe('50대 수준')
  })

  it('단계가 같으면 점수 높은 쪽, 그것도 같으면 당뇨', () => {
    expect(pickHomeHealthAge(latest([row({ score: 31 }), row({ id: 2, disease: 'HYPERTENSION', score: 40 })]))?.disease).toBe(
      'HYPERTENSION',
    )
    expect(pickHomeHealthAge(latest([row({ id: 2, disease: 'HYPERTENSION' }), row({})]))?.disease).toBe('DIABETES')
  })

  it('기준표 행·건강 나이 null은 후보가 아님', () => {
    const picked = pickHomeHealthAge(
      latest([
        row({ disease: 'HYPERTENSION', level: 'HIGH', score: 70, health_age: null }),
        row({ id: 2, method: 'CHECKUP_CRITERIA', score: null, level: 'HIGH', health_age: null }),
        row({ id: 3, level: 'LOW', score: 10 }),
      ]),
    )
    expect(picked?.disease).toBe('DIABETES')
  })

  it('진단받은 질환은 행이 없어서 빠지고, 후보가 없으면 null', () => {
    expect(pickHomeHealthAge({ ...latest([]), managed_diseases: ['DIABETES', 'HYPERTENSION'] })).toBeNull()
  })
})

describe('homeDateLabel', () => {
  it('서울 기준 "11월 25일 수요일"', () => {
    expect(homeDateLabel(new Date('2026-11-25T01:00:00Z'))).toBe('11월 25일 수요일')
  })

  it('UTC 전날 밤이어도 서울 날짜로', () => {
    expect(homeDateLabel(new Date('2026-11-24T16:30:00Z'))).toBe(homeDateLabel(new Date('2026-11-25T03:00:00Z')))
  })
})

describe('usedSources', () => {
  it('본문에 나온 번호의 출처만', () => {
    const sources = [
      { number: 1, title: 'A' },
      { number: 2, title: 'B' },
    ]
    expect(usedSources('계단으로 올라가 볼까요? [2]', sources)).toEqual([{ number: 2, title: 'B' }])
    expect(usedSources('근거가 충분하지 않아요.', sources)).toEqual([])
  })
})
