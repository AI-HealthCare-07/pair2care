// frontend/src/records/riskTrend.test.ts
// 위험도 추이 카드 규칙: 낮아졌을 때만 문구, 달라진 응답 문구, 주 이름

import { describe, expect, it } from 'vitest'
import type { TrendPoint } from '../api/dashboard'
import type { ModelPredictionDetail } from '../api/predictions'
import { barPercent, changedInputText, dropNote, droppedPrediction, weekLabel } from './riskTrend'

const point = (score: number, id: number): TrendPoint => ({
  week_start: '2026-11-16',
  score,
  level: 'CAUTION',
  prediction_id: id,
  criteria_level: null,
})

describe('droppedPrediction (REQ-NFR-003)', () => {
  it('마지막이 직전보다 낮을 때만 그 예측 id', () => {
    expect(droppedPrediction([point(61, 1), point(58, 2)])).toBe(2)
    expect(droppedPrediction([point(58, 1), point(58, 2)])).toBeNull() // 그대로
    expect(droppedPrediction([point(50, 1), point(55, 2)])).toBeNull() // 높아짐
    expect(droppedPrediction([point(50, 1)])).toBeNull() // 점 하나
  })
})

describe('changedInputText', () => {
  it('숫자는 단위를 뒤에 한 번, 보기는 설문 문구로', () => {
    expect(
      changedInputText([
        { feature: 'weight_kg', before: 80, after: 78.2 },
        { feature: 'alcohol_frequency', before: 5, after: 4 },
      ]),
    ).toBe('체중 80 → 78.2kg · 술 마시는 횟수 주 2~3회 → 월 2~4회')
  })

  it('모르는 항목은 건너뛰고, null은 "응답 없음"', () => {
    expect(changedInputText([{ feature: 'sex', before: 1, after: 2 }])).toBe('')
    expect(changedInputText([{ feature: 'alcohol_amount', before: null, after: 1 }])).toBe('한 번에 마시는 양 응답 없음 → 1~2잔')
  })
})

describe('막대·주 이름', () => {
  it('막대는 최소 6%, 최대 100%', () => {
    expect(barPercent(0)).toBe(6)
    expect(barPercent(45)).toBe(45)
    expect(barPercent(120)).toBe(100)
  })

  it('주 이름은 그 주 월요일', () => {
    expect(weekLabel('2026-11-16')).toBe('11/16 주')
  })
})

describe('dropNote (#147 리뷰: 문구와 달라진 응답의 기준을 맞춤)', () => {
  const detail = (score: number, previousScore: number | null, changes = [{ feature: 'weight_kg', before: 80, after: 78 }]): ModelPredictionDetail => ({
    id: 3,
    disease: 'HYPERTENSION',
    level: 'CAUTION',
    model_version: 'hypertension_risk:v2',
    created_at: '2026-11-27T09:00:00+09:00',
    method: 'MODEL',
    score,
    factors: [],
    changed_inputs: previousScore === null ? null : changes,
    previous: previousScore === null ? null : { id: 2, score: previousScore, level: 'CAUTION', created_at: '2026-11-26T09:00:00+09:00' },
    health_age: null,
  })

  it('직전 예측(previous)보다 낮을 때만 문구', () => {
    expect(dropNote(detail(55, 60))).toBe('달라진 응답: 체중 80 → 78kg')
  })

  it('막대는 60→58로 내려가도 직전(같은 주 WEEKLY 50)보다 오르면 문구 없음', () => {
    expect(dropNote(detail(58, 50, [{ feature: 'weight_kg', before: 78, after: 80 }]))).toBeNull()
  })

  it('previous가 없거나 같으면 문구 없음, 달라진 응답이 없어도 문구 없음', () => {
    expect(dropNote(detail(55, null))).toBeNull()
    expect(dropNote(detail(55, 55))).toBeNull()
    expect(dropNote(detail(55, 60, []))).toBeNull()
  })
})
