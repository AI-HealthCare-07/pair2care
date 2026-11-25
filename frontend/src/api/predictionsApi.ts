// frontend/src/api/predictionsApi.ts
// 예측 화면(S-09)은 predictions.ts나 predictions.mock.ts를 직접 부르지 않고 이 파일의 predictionsApi만 씀.
// frontend/.env.local 에 VITE_USE_MOCK=true 를 넣으면 가짜 데이터, 없으면(또는 false) 진짜 서버.
// 가짜 쪽은 동적 import라서 운영 빌드에는 들어가지 않음 (mealsApi.ts·healthProfilesApi.ts와 같은 방식).

import * as real from './predictions'
import type { MockPredictionScenario } from './predictions.mockScenarios'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const loadMock = () => import('./predictions.mock')

export const predictionsApi = {
  getLatestPredictions: (...args: Parameters<typeof real.getLatestPredictions>) =>
    useMock ? loadMock().then((m) => m.getLatestPredictions(...args)) : real.getLatestPredictions(...args),
  getPrediction: (...args: Parameters<typeof real.getPrediction>) =>
    useMock ? loadMock().then((m) => m.getPrediction(...args)) : real.getPrediction(...args),

  /** 개발용(가짜 모드에서만 동작): 가짜 응답 경우 바꾸기. 진짜 모드에서는 아무것도 안 함 */
  setMockScenario: (scenario: MockPredictionScenario): Promise<void> =>
    useMock ? loadMock().then((m) => m.setMockPredictionScenario(scenario)) : Promise.resolve(),
}
