// frontend/src/api/mealsApi.ts
// 화면은 meals.ts나 meals.mock.ts를 직접 부르지 않고 이 파일의 mealsApi만 씀.
// frontend/.env.local 에 VITE_USE_MOCK=true 를 넣으면 가짜 데이터, 없으면(또는 false) 진짜 서버.
// (.env.local은 git에 올라가지 않는지 .gitignore 확인)
//
// 가짜 쪽(meals.mock)은 동적 import라서, VITE_USE_MOCK이 true가 아닌 운영 빌드에는 들어가지 않음.
// 대신 모든 함수가 Promise를 돌려줌 (진짜 API도 원래 Promise라 화면 코드는 그대로).

import * as real from './meals'
import type { MealTaskEvent } from './meals'
import { MOCK_DATE } from './meals.mockDate'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const loadMock = () => import('./meals.mock')

export const mealsApi = {
  /** 가짜 모드일 때만 값이 있음: 가짜 데이터가 들어 있는 날짜. 진짜 모드는 undefined(→ 오늘 날짜 사용) */
  demoDate: useMock ? MOCK_DATE : undefined,

  uploadMeal: (...args: Parameters<typeof real.uploadMeal>) =>
    useMock ? loadMock().then((m) => m.uploadMeal(...args)) : real.uploadMeal(...args),
  retryMeal: (...args: Parameters<typeof real.retryMeal>) =>
    useMock ? loadMock().then((m) => m.retryMeal(...args)) : real.retryMeal(...args),
  listMeals: (...args: Parameters<typeof real.listMeals>) =>
    useMock ? loadMock().then((m) => m.listMeals(...args)) : real.listMeals(...args),
  getMeal: (...args: Parameters<typeof real.getMeal>) =>
    useMock ? loadMock().then((m) => m.getMeal(...args)) : real.getMeal(...args),
  updateMeal: (...args: Parameters<typeof real.updateMeal>) =>
    useMock ? loadMock().then((m) => m.updateMeal(...args)) : real.updateMeal(...args),
  deleteMeal: (...args: Parameters<typeof real.deleteMeal>) =>
    useMock ? loadMock().then((m) => m.deleteMeal(...args)) : real.deleteMeal(...args),
  listFoods: (...args: Parameters<typeof real.listFoods>) =>
    useMock ? loadMock().then((m) => m.listFoods(...args)) : real.listFoods(...args),

  /**
   * 분류 결과 알림(SSE task 이벤트) 구독. 반환값은 해제 함수.
   * 가짜 모드: meals.mock의 알림 흉내를 연결.
   * 진짜 모드: shortcut — 공통 SSE 훅(api.md 12-6)이 생길 때까지 아무것도 안 함(빈 함수).
   *            훅이 생기면 여기서 연결하고, 화면(S-22)의 2초 조회는 이 구독으로 바꿈.
   */
  subscribeTasks: (cb: (e: MealTaskEvent) => void): (() => void) => {
    if (!useMock) return () => undefined
    let cancelled = false
    let off: () => void = () => undefined
    void loadMock().then((m) => {
      if (!cancelled) off = m.subscribeMockTasks(cb)
    })
    return () => {
      cancelled = true
      off()
    }
  },
}
