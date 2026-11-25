// frontend/src/api/healthProfilesApi.ts
// 설문 화면은 healthProfiles.ts나 healthProfiles.mock.ts를 직접 부르지 않고 이 파일의 healthProfilesApi만 씀.
// frontend/.env.local 에 VITE_USE_MOCK=true 를 넣으면 가짜 데이터, 없으면(또는 false) 진짜 서버.
// 가짜 쪽은 동적 import라서 운영 빌드에는 들어가지 않음 (mealsApi.ts와 같은 방식).

import * as real from './healthProfiles'
import type { ApiError } from './client'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const loadMock = () => import('./healthProfiles.mock')

export const healthProfilesApi = {
  getSurveyDefinition: (...args: Parameters<typeof real.getSurveyDefinition>) =>
    useMock ? loadMock().then((m) => m.getSurveyDefinition(...args)) : real.getSurveyDefinition(...args),
  postHealthProfile: (...args: Parameters<typeof real.postHealthProfile>) =>
    useMock ? loadMock().then((m) => m.postHealthProfile(...args)) : real.postHealthProfile(...args),

  /** 개발용(가짜 모드에서만 동작): 다음 저장 요청을 이 에러로 실패시킴. null이면 해제 */
  setMockNextError: (err: ApiError | null): Promise<void> =>
    useMock ? loadMock().then((m) => m.setMockSurveyError(err)) : Promise.resolve(),
}
