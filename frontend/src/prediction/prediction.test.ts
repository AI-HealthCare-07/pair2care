// frontend/src/prediction/prediction.test.ts
// S-09 화면 상태(view)·건강 나이 문구(healthAge)·요인 문구(labels)·가짜 API 모양
// 근거: api.md 5-2·5-3·5-5, #102(건강 나이), #107(요인에서 나이 제외·문구 14개), 11/25 팀장님·현영 님·성은 님 답

import { beforeAll, describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import type { HealthAge, LatestPrediction, LatestPredictionsResponse } from '../api/predictions'
import {
  getLatestPredictions,
  getPrediction,
  retryPredictions,
  setMockPredictionDelay,
  setMockPredictionScenario,
} from '../api/predictions.mock'
import { MOCK_PREDICTION_SCENARIOS } from '../api/predictions.mockScenarios'
import { decadeOf, healthAgeLine } from './healthAge'
import {
  checkupHeading,
  CHECKUP_ADVICE,
  CHECKUP_RANGE_TEXT,
  DISEASE_ORDER,
  LEVEL_MESSAGE,
  FAILED_MESSAGE,
  factorText,
  LEVEL_LABEL,
  metabolicMessage,
  yearsText,
} from './labels'
import {
  buildPredictionView,
  CAUTION_MIN_SCORE,
  checkupLink,
  checkupPrompt,
  levelMessage,
  metabolicView,
  factorLines,
  GAUGE_LABEL_PERCENT,
  gaugePercent,
  HIGH_MIN_SCORE,
  retryFailureAction,
} from './view'

const row = (overrides: Partial<LatestPrediction>): LatestPrediction => ({
  id: 1,
  disease: 'DIABETES',
  method: 'MODEL',
  score: 34,
  level: 'CAUTION',
  health_age: null,
  created_at: '2026-11-19T10:40:00+09:00',
  ...overrides,
})

const latest = (overrides: Partial<LatestPredictionsResponse>): LatestPredictionsResponse => ({
  health_profile_id: 31,
  predictions: [],
  managed_diseases: [],
  skipped_reason: null,
  metabolic_syndrome: null,
  ...overrides,
})

const age = (decade: number | null, out_of_range: HealthAge['out_of_range'], actual_age: number): HealthAge => ({
  decade,
  actual_age,
  out_of_range,
})

describe('buildPredictionView (5-2 → 화면 상태)', () => {
  it('임신·나이 범위 밖은 일반 안내 (M04-b)', () => {
    expect(buildPredictionView(latest({ skipped_reason: 'PREGNANT' }))).toEqual({ kind: 'GENERAL', reason: 'PREGNANT' })
    expect(buildPredictionView(latest({ skipped_reason: 'AGE_OUT_OF_RANGE' }))).toEqual({
      kind: 'GENERAL',
      reason: 'AGE_OUT_OF_RANGE',
    })
  })

  it('predictions·managed_diseases 둘 다 비어 있고 이유 없음 → 예측 실패', () => {
    expect(buildPredictionView(latest({}))).toEqual({ kind: 'FAILED' })
  })

  it('카드 순서는 고혈압 → 당뇨 (서버는 당뇨 → 고혈압으로 줌)', () => {
    const view = buildPredictionView(
      latest({ predictions: [row({ id: 51, disease: 'DIABETES' }), row({ id: 52, disease: 'HYPERTENSION' })] }),
    )
    expect(view.kind === 'RESULT' && view.cards.map((c) => c.disease)).toEqual(['HYPERTENSION', 'DIABETES'])
  })

  it('모델 행과 기준표 행을 질환별로 묶음', () => {
    const view = buildPredictionView(
      latest({
        predictions: [
          row({ id: 52, disease: 'HYPERTENSION' }),
          row({ id: 53, disease: 'HYPERTENSION', method: 'CHECKUP_CRITERIA', score: null, checkup_record_id: 8 }),
          row({ id: 51, disease: 'DIABETES' }),
        ],
      }),
    )
    if (view.kind !== 'RESULT') throw new Error('RESULT여야 함')
    const [htn, dm] = view.cards
    expect(htn.kind === 'RESULT' && [htn.model.id, htn.checkup?.id]).toEqual([52, 53])
    expect(dm.kind === 'RESULT' && dm.checkup).toBeNull()
  })

  it('진단 "예"인 질환은 관리 중 카드, 둘 다 관리 중이어도 실패가 아님', () => {
    const one = buildPredictionView(latest({ predictions: [row({ disease: 'HYPERTENSION' })], managed_diseases: ['DIABETES'] }))
    expect(one.kind === 'RESULT' && one.cards.map((c) => c.kind)).toEqual(['RESULT', 'MANAGED'])

    const both = buildPredictionView(latest({ managed_diseases: ['DIABETES', 'HYPERTENSION'] }))
    expect(both.kind === 'RESULT' && both.cards.map((c) => c.kind)).toEqual(['MANAGED', 'MANAGED'])
  })

  it('한 질환만 모델 행이 없으면 그 카드만 MISSING', () => {
    const view = buildPredictionView(latest({ predictions: [row({ disease: 'HYPERTENSION' })] }))
    expect(view.kind === 'RESULT' && view.cards.map((c) => c.kind)).toEqual(['RESULT', 'MISSING'])
  })
})

describe('gaugePercent', () => {
  it('점수 그대로 0~100, 범위 밖은 자름, 점수 없으면 null', () => {
    expect(gaugePercent(34)).toBe(34)
    expect(gaugePercent(0)).toBe(0)
    expect(gaugePercent(100)).toBe(100)
    expect(gaugePercent(130)).toBe(100)
    expect(gaugePercent(null)).toBeNull()
  })
})

describe('게이지 글자 위치 (#111 성은 님)', () => {
  it('단계 기준 30·60 (서버 model.py와 같음), 글자는 구간 가운데 15·45·80%', () => {
    expect([CAUTION_MIN_SCORE, HIGH_MIN_SCORE]).toEqual([30, 60])
    expect(GAUGE_LABEL_PERCENT).toEqual({ LOW: 15, CAUTION: 45, HIGH: 80 })
  })

  it('글자는 자기 단계 구간 안에 있음 (62점 HIGH 원은 60% 구분선 오른쪽 = "높음" 구간)', () => {
    expect(GAUGE_LABEL_PERCENT.LOW).toBeLessThan(CAUTION_MIN_SCORE)
    expect(GAUGE_LABEL_PERCENT.CAUTION).toBeGreaterThanOrEqual(CAUTION_MIN_SCORE)
    expect(GAUGE_LABEL_PERCENT.CAUTION).toBeLessThan(HIGH_MIN_SCORE)
    expect(GAUGE_LABEL_PERCENT.HIGH).toBeGreaterThanOrEqual(HIGH_MIN_SCORE)
    expect(gaugePercent(62)).toBeGreaterThanOrEqual(HIGH_MIN_SCORE)
  })
})

describe('healthAgeLine (건강 나이 한 줄)', () => {
  it('null이면 줄 숨김 (기준표 행·곡선 읽기 실패·예전 모델 행)', () => {
    expect(healthAgeLine(null)).toBeNull()
  })

  it('같은 10살 구간이면 "비슷한 수준" (45세·40대)', () => {
    expect(healthAgeLine(age(40, null, 45))).toEqual({
      level: '40대 수준',
      compare: 'SIMILAR',
      compareText: '실제 나이와 비슷한 수준이에요',
    })
  })

  it('구간이 다를 때만 높게 / 낮게 (45세: 50대 높게, 30대 낮게)', () => {
    expect(healthAgeLine(age(50, null, 45))?.compare).toBe('HIGHER')
    expect(healthAgeLine(age(30, null, 45))?.compare).toBe('LOWER')
  })

  it('구간 경계: 49세·50대는 높게, 50세·50대는 비슷', () => {
    expect(healthAgeLine(age(50, null, 49))?.compare).toBe('HIGHER')
    expect(healthAgeLine(age(50, null, 50))?.compare).toBe('SIMILAR')
  })

  it('곡선 밖: BELOW "30세 미만 수준"은 늘 낮게, ABOVE "69세 초과 수준"은 늘 높게', () => {
    expect(healthAgeLine(age(null, 'BELOW', 30))).toMatchObject({ level: '30세 미만 수준', compare: 'LOWER' })
    expect(healthAgeLine(age(null, 'ABOVE', 69))).toMatchObject({ level: '69세 초과 수준', compare: 'HIGHER' })
  })

  it('decade·out_of_range 둘 다 없으면 숨김', () => {
    expect(healthAgeLine(age(null, null, 45))).toBeNull()
  })

  it('decadeOf: 만 나이 → 10살 구간', () => {
    expect([decadeOf(30), decadeOf(39), decadeOf(45), decadeOf(69)]).toEqual([30, 30, 40, 60])
  })
})

describe('요인 문구 (#107)', () => {
  it('7개 feature × UP/DOWN = 14개 모두 문구가 있음', () => {
    const features = [
      'bmi',
      'father_diabetes_history',
      'mother_hypertension_history',
      'sibling_diabetes_history',
      'alcohol_frequency',
      'alcohol_amount',
      'smoking_current',
    ]
    for (const feature of features) {
      for (const direction of ['UP', 'DOWN'] as const) {
        expect(factorText({ feature, direction }), `${feature} ${direction}`).toBeTruthy()
      }
    }
  })

  it('가족력은 질환 상관없이 "누구의 가족력"', () => {
    expect(factorText({ feature: 'father_diabetes_history', direction: 'UP' })).toBe('아버지 가족력이 있어요')
    expect(factorText({ feature: 'father_hypertension_history', direction: 'UP' })).toBe('아버지 가족력이 있어요')
    expect(factorText({ feature: 'sibling_hypertension_history', direction: 'DOWN' })).toBe('형제자매 가족력이 없어요')
  })

  it('술 DOWN은 안 마시는 분에게도 맞는 문장 (양은 "한 번에" 없음)', () => {
    expect(factorText({ feature: 'alcohol_amount', direction: 'DOWN', years: -1 })).toBe('술 마시는 양이 같은 성별 평균보다 적어요')
    expect(factorText({ feature: 'alcohol_amount', direction: 'UP', years: 1 })).toBe('한 번에 마시는 양이 같은 성별 평균보다 많아요')
    expect(factorText({ feature: 'alcohol_frequency', direction: 'DOWN', years: -1 })).toBe('술 마시는 횟수가 같은 성별 평균보다 적어요')
  })

  it('age·sex·모르는 값은 null → 건너뜀 (#107 전에 저장된 행)', () => {
    expect(factorText({ feature: 'age', direction: 'UP' })).toBeNull()
    expect(factorText({ feature: 'sex', direction: 'DOWN' })).toBeNull()
    expect(factorText({ feature: 'mystery', direction: 'UP' })).toBeNull()
  })

  it('factorLines: 모르는 값은 빼고 순서 유지, 최대 3개, null·빈 배열은 []', () => {
    const lines = factorLines([
      { feature: 'age', direction: 'UP' },
      { feature: 'bmi', direction: 'UP' },
      { feature: 'smoking_current', direction: 'DOWN' },
    ])
    expect(lines.map((l) => l.text)).toEqual(['체중(BMI)이 평균보다 높아요', '지금 담배를 피우지 않아요']) // years 없음 = 옛 기준
    expect(factorLines(null)).toEqual([])
    expect(factorLines([])).toEqual([])
  })
})

describe('가감 나이 years (#114·#121)', () => {
  it('yearsText: 양수 "+5살", 음수 "−1살"(U+2212), 0·null·없음은 숨김', () => {
    expect(yearsText(5)).toBe('+5살')
    expect(yearsText(-1)).toBe('\u22121살')
    expect(yearsText(0)).toBeNull()
    expect(yearsText(null)).toBeNull()
    expect(yearsText(undefined)).toBeNull()
  })

  it('체중·음주 4개는 "같은 성별 평균", 가족력·흡연은 그대로 (#114 성은 님)', () => {
    expect(factorText({ feature: 'bmi', direction: 'DOWN', years: -2 })).toBe('체중(BMI)이 같은 성별 평균보다 낮아요')
    expect(factorText({ feature: 'alcohol_frequency', direction: 'UP', years: 1 })).toBe('술 마시는 횟수가 같은 성별 평균보다 많아요')
    expect(factorText({ feature: 'father_diabetes_history', direction: 'UP' })).toBe('아버지 가족력이 있어요')
    expect(factorText({ feature: 'smoking_current', direction: 'DOWN' })).toBe('지금 담배를 피우지 않아요')
  })

  it('years가 null·없음이면 옛 기준(남녀 합친 평균)이라 체중·음주는 "같은 성별" 없이 (#123 현영 님)', () => {
    expect(factorText({ feature: 'bmi', direction: 'UP', years: null })).toBe('체중(BMI)이 평균보다 높아요')
    expect(factorText({ feature: 'alcohol_frequency', direction: 'DOWN' })).toBe('술 마시는 횟수가 평균보다 적어요')
    expect(factorText({ feature: 'alcohol_amount', direction: 'DOWN', years: null })).toBe('술 마시는 양이 평균보다 적어요')
    expect(factorText({ feature: 'mother_diabetes_history', direction: 'UP', years: null })).toBe('어머니 가족력이 있어요')
    expect(factorText({ feature: 'smoking_current', direction: 'UP', years: null })).toBe('지금 담배를 피워요')
  })

  it('factorLines가 years를 붙이고, null·키 없음(예전 응답)이면 숫자 없이', () => {
    const lines = factorLines([
      { feature: 'father_diabetes_history', direction: 'UP', years: 5 },
      { feature: 'smoking_current', direction: 'DOWN', years: -2 },
      { feature: 'bmi', direction: 'UP', years: null },
      { feature: 'alcohol_frequency', direction: 'UP' },
    ])
    expect(lines.map((l) => l.years)).toEqual(['+5살', '\u22122살', null])
  })
})

describe('문구 상수', () => {
  it('단계 글자 3개 (색만으로 구분 X)', () => {
    expect(LEVEL_LABEL).toEqual({ LOW: '낮음', CAUTION: '주의', HIGH: '높음' })
  })

  it('질환 순서는 고혈압 → 당뇨', () => {
    expect(DISEASE_ORDER).toEqual(['HYPERTENSION', 'DIABETES'])
  })
})

describe('가짜 API (predictions.mock)', () => {
  beforeAll(() => setMockPredictionDelay(0))

  it.each(MOCK_PREDICTION_SCENARIOS.filter((s) => s !== 'no_survey'))(
    '%s: 5-2의 모든 행을 5-3으로 열 수 있고, 같은 id·질환·단계·건강 나이',
    async (scenario) => {
      setMockPredictionScenario(scenario)
      const res = await getLatestPredictions()
      for (const p of res.predictions) {
        const detail = await getPrediction(p.id)
        expect(detail).toMatchObject({ id: p.id, disease: p.disease, method: p.method, level: p.level })
        expect(detail.health_age).toEqual(p.health_age)
        if (p.method === 'CHECKUP_CRITERIA') expect(p.health_age).toBeNull()
      }
    },
  )

  it('no_survey: 5-2가 404', async () => {
    setMockPredictionScenario('no_survey')
    await expect(getLatestPredictions()).rejects.toMatchObject({ status: 404 })
  })

  it('없는 id는 404', async () => {
    setMockPredictionScenario('normal')
    await expect(getPrediction(999)).rejects.toMatchObject({ status: 404 })
  })
})

describe('다시 계산 (5-5)', () => {
  beforeAll(() => setMockPredictionDelay(0))

  it.each([
    [409, 'RELOAD'],
    [404, 'ONBOARDING'],
    [401, 'STAY_FAILED'], // 세션 만료는 가드가 /login으로 (#134)
    [503, 'STAY_FAILED'],
    [0, 'STAY_FAILED'], // 시간 초과(#130)
    [500, 'STAY_FAILED'],
  ] as const)('%i → %s', (status, action) => {
    expect(retryFailureAction(new ApiError(status, '문구'))).toBe(action)
  })

  it('ApiError가 아니면(연결 끊김 등) 실패 화면 그대로', () => {
    expect(retryFailureAction(new TypeError('Failed to fetch'))).toBe('STAY_FAILED')
  })

  it('문구에 "준비 중"이 남아 있지 않음', () => {
    expect(FAILED_MESSAGE).not.toContain('준비 중')
  })

  it('가짜 failed: 다시 계산 성공 → 5-2가 결과로 바뀌고, 다시 부르면 409', async () => {
    setMockPredictionScenario('failed')
    setMockPredictionScenario('normal')
    setMockPredictionScenario('failed') // 다른 경우를 거쳐 처음 상태로
    expect(buildPredictionView(await getLatestPredictions()).kind).toBe('FAILED')
    await retryPredictions()
    setMockPredictionScenario('failed') // 화면이 다시 불러올 때처럼 같은 이름으로 불러도 유지
    expect(buildPredictionView(await getLatestPredictions()).kind).toBe('RESULT')
    await expect(retryPredictions()).rejects.toMatchObject({ status: 409 })
  })

  it('가짜 failed_again: 503이고 실패 그대로', async () => {
    setMockPredictionScenario('failed_again')
    await expect(retryPredictions()).rejects.toMatchObject({ status: 503 })
    expect(buildPredictionView(await getLatestPredictions()).kind).toBe('FAILED')
  })

  it('가짜 no_survey: 404', async () => {
    setMockPredictionScenario('no_survey')
    await expect(retryPredictions()).rejects.toMatchObject({ status: 404 })
  })
})

describe('검진 기준표 줄 · S-07 링크 (12/4, api.md 5-1)', () => {
  const ms = (status: 'MET' | 'NOT_MET' | 'UNKNOWN', met_count: number, missing: string[]) => ({ status, met_count, missing })

  it('기준표 행이 있으면 링크 없음, 없으면 링크', () => {
    const view = buildPredictionView(
      latest({
        predictions: [
          row({ id: 52, disease: 'HYPERTENSION' }),
          row({ id: 53, disease: 'HYPERTENSION', method: 'CHECKUP_CRITERIA', score: null, checkup_record_id: 8 }),
          row({ id: 51, disease: 'DIABETES' }),
        ],
        metabolic_syndrome: ms('UNKNOWN', 2, ['triglyceride', 'hdl_cholesterol']),
      }),
    )
    if (view.kind !== 'RESULT') throw new Error('RESULT여야 함')
    const [htn, dm] = view.cards
    expect(htn.kind === 'RESULT' && htn.prompt).toBeNull()
    expect(dm.kind === 'RESULT' && dm.prompt).toEqual({ kind: 'MORE', focus: 'hba1c' })
  })

  it('유효한 검진 없음(대사증후군 null) → NONE, 질환 첫 칸', () => {
    expect(checkupPrompt('HYPERTENSION', null)).toEqual({ kind: 'NONE', focus: 'systolic_bp' })
    expect(checkupPrompt('DIABETES', null)).toEqual({ kind: 'NONE', focus: 'fasting_glucose' })
  })

  it('검진은 있는데 판정 없음 → MORE. 당뇨는 공복혈당이 빠졌으면 공복혈당, 아니면 당화혈색소', () => {
    expect(checkupPrompt('HYPERTENSION', ms('UNKNOWN', 1, ['blood_pressure']))).toEqual({ kind: 'MORE', focus: 'systolic_bp' })
    expect(checkupPrompt('DIABETES', ms('UNKNOWN', 1, ['fasting_glucose']))).toEqual({ kind: 'MORE', focus: 'fasting_glucose' })
    expect(checkupPrompt('DIABETES', ms('NOT_MET', 0, []))).toEqual({ kind: 'MORE', focus: 'hba1c' })
  })

  it('링크 주소는 S-07 ?focus= (#153)', () => {
    expect(checkupLink('triglyceride')).toBe('/checkup?focus=triglyceride')
  })

  it('기준표 문구에 "진단"이 없음, 질환별 범위 이름', () => {
    expect(CHECKUP_RANGE_TEXT.HYPERTENSION.HIGH).toBe('혈압이 고혈압 범위예요')
    expect(CHECKUP_RANGE_TEXT.DIABETES.CAUTION).toBe('혈당이 주의 범위예요')
    for (const disease of DISEASE_ORDER) {
      for (const text of Object.values(CHECKUP_RANGE_TEXT[disease])) expect(text).not.toContain('진단')
    }
  })

  it('모델 낮음 + 기준표 주의·높음이면 단계 한 줄에서 "유지해도 좋아요"를 뺌 (#157 성은 님)', () => {
    expect(levelMessage('LOW', 'HIGH')).toBe('상대적으로 낮은 편이에요')
    expect(levelMessage('LOW', 'CAUTION')).toBe('상대적으로 낮은 편이에요')
    expect(levelMessage('LOW', 'LOW')).toBe(LEVEL_MESSAGE.LOW)
    expect(levelMessage('LOW', null)).toBe(LEVEL_MESSAGE.LOW)
    expect(levelMessage('CAUTION', 'HIGH')).toBe(LEVEL_MESSAGE.CAUTION)
  })

  it('병원 권유는 모델 높음 한 줄과 같은 문장 (#157)', () => {
    expect(CHECKUP_ADVICE).toBe(LEVEL_MESSAGE.HIGH)
  })

  it('검진 날짜는 점으로, 못 불러오면 날짜 없이', () => {
    expect(checkupHeading('2026-05-10')).toBe('검진 수치(2026.05.10) 기준')
    expect(checkupHeading(null)).toBe('검진 수치 기준')
  })
})

describe('대사증후군 카드 (api.md 5-1)', () => {
  it('null이면 카드 숨김', () => {
    expect(metabolicView(null)).toBeNull()
    expect(buildPredictionView(latest({ predictions: [row({})] }))).toMatchObject({ metabolic: null })
  })

  it('판단 어려움: 빠진 항목 이름 + 첫 빠진 칸 링크. 기준 이름 → 입력칸 이름 (waist → waist_cm, blood_pressure → systolic_bp)', () => {
    expect(metabolicView({ status: 'UNKNOWN', met_count: 2, missing: ['triglyceride', 'hdl_cholesterol'] })).toEqual({
      status: 'UNKNOWN',
      metCount: 2,
      missingLabels: ['중성지방', 'HDL'],
      focus: 'triglyceride',
    })
    expect(metabolicView({ status: 'UNKNOWN', met_count: 1, missing: ['waist', 'blood_pressure'] })?.focus).toBe('waist_cm')
    expect(metabolicView({ status: 'UNKNOWN', met_count: 2, missing: ['blood_pressure'] })?.focus).toBe('systolic_bp')
  })

  it('해당·해당 아님은 빠진 항목이 있어도 링크 없음, 모르는 기준 이름은 뺌', () => {
    expect(metabolicView({ status: 'MET', met_count: 3, missing: ['hdl_cholesterol'] })?.focus).toBeNull()
    expect(metabolicView({ status: 'NOT_MET', met_count: 0, missing: ['waist', 'triglyceride'] })?.focus).toBeNull()
    expect(metabolicView({ status: 'UNKNOWN', met_count: 2, missing: ['ldl'] })).toMatchObject({ missingLabels: [], focus: null })
  })

  it('문구: Figma 예시 그대로, 을/를은 받침으로', () => {
    expect(metabolicMessage('UNKNOWN', 2, ['중성지방', 'HDL'])).toBe('5개 기준 중 2개 해당. 중성지방·HDL을 넣으면 알 수 있어요')
    expect(metabolicMessage('UNKNOWN', 1, ['허리둘레'])).toBe('5개 기준 중 1개 해당. 허리둘레를 넣으면 알 수 있어요')
    expect(metabolicMessage('UNKNOWN', 2, ['공복혈당'])).toBe('5개 기준 중 2개 해당. 공복혈당을 넣으면 알 수 있어요')
    expect(metabolicMessage('NOT_MET', 1, ['waist'])).toBe('5개 기준 중 1개 해당')
    expect(metabolicMessage('MET', 3, [])).toContain('병원')
  })
})
