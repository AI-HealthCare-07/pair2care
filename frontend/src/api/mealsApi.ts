// frontend/src/api/mealsApi.ts
// 화면은 meals.ts나 meals.mock.ts를 직접 부르지 않고 이 파일의 mealsApi만 씀.
// frontend/.env.local 에 VITE_USE_MOCK=true 를 넣으면 가짜 데이터, 없으면(또는 false) 진짜 서버.
// (.env.local은 git에 올라가지 않는지 .gitignore 확인)

import * as real from './meals'
import * as mock from './meals.mock'

const impl = import.meta.env.VITE_USE_MOCK === 'true' ? mock : real

export const mealsApi = {
  uploadMeal: impl.uploadMeal,
  retryMeal: impl.retryMeal,
  listMeals: impl.listMeals,
  getMeal: impl.getMeal,
  updateMeal: impl.updateMeal,
  deleteMeal: impl.deleteMeal,
  listFoods: impl.listFoods,
}
