// frontend/src/api/predictions.mockScenarios.ts
// 가짜 예측 응답의 경우 이름. predictionsApi.ts가 가짜 데이터(predictions.mock.ts)를 정적으로 import하지 않고도
// 이름을 쓸 수 있게 따로 둔 작은 파일 (meals.mockDate.ts와 같은 이유).

export const MOCK_PREDICTION_SCENARIOS = [
  'normal', // 고혈압 주의(건강 나이 높게) · 당뇨 낮음(30세 미만 수준)
  'similar', // 고혈압 낮음(비슷한 수준, 요인 0개) · 당뇨 높음(69세 초과 수준, 요인 1개 + 예전 행의 age, years 없음)
  'health_age_null', // 건강 나이 null + 요인 years null (means_by_sex 없음·예전 모델 행) → 줄·숫자 숨김 확인
  'managed_one', // 당뇨 진단 "예" → 당뇨는 관리 중, 고혈압만 결과
  'managed_both', // 둘 다 관리 중
  'pregnant', // 일반 안내 (M04-b)
  'age_out', // 일반 안내 (M04-b)
  'failed', // 예측 실패 (행 없음 + 관리 중 없음 + skipped_reason null). "다시 계산"하면 성공 → normal 결과
  'failed_again', // 예측 실패 + "다시 계산"도 503 → 실패 화면 그대로 + 안내 문구
  'partial_failed', // 고혈압만 행이 있고 당뇨는 실패
  'checkup', // 기준표 행 + 대사증후군 (12/4 범위 확인용)
  'no_survey', // 5-2 404
] as const

export type MockPredictionScenario = (typeof MOCK_PREDICTION_SCENARIOS)[number]
