// frontend/src/api/meals.mock.ts
// 백엔드가 없을 때 쓰는 가짜 식단 API. meals.ts와 함수 이름·시그니처가 같음.
// ⚠️ 영양값은 화면 확인용 임시 값입니다. 육개장·잔치국수는 api.md 10장 예시 값,
//    닭개장은 탄수화물·지방 null(실제와 같음), 나머지는 1인분·kcal·나트륨만 실제 값(1인분 근거 표)이고
//    탄수화물·당류·단백질·지방은 가짜 숫자입니다.

import {
  MealApiError,
  type Food,
  type FeedbackItem,
  type FeedbackKey,
  type FeedbackLevel,
  type MealCandidate,
  type MealDetail,
  type MealFeedback,
  type MealListItem,
  type MealListResponse,
  type MealTaskEvent,
  type MealTaskResponse,
  type Nutrients,
  type Portion,
  type UpdateMealBody,
} from './meals'

// ─────────────────────────────────────────────
// 설정 · 유틸
// ─────────────────────────────────────────────

/** 가짜 데이터가 들어 있는 날짜. 다른 날짜로 listMeals를 부르면 빈 목록 */
export const MOCK_DATE = '2026-11-19'

const NUTRIENT_KEYS = ['kcal', 'carbs_g', 'sugar_g', 'sodium_mg', 'protein_g', 'fat_g'] as const
const FEEDBACK_KEYS: FeedbackKey[] = ['sodium_mg', 'sugar_g', 'carbs_g']
const DAILY_REFERENCE: Record<FeedbackKey, number> = { sodium_mg: 2000, sugar_g: 100, carbs_g: 324 }

const wait = (ms = 250) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const round1 = (n: number) => Math.round(n * 10) / 10
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T
const at = (hhmm: string) => `${MOCK_DATE}T${hhmm}:00+09:00`

/** 화면에서 진단 여부별 강조를 바꿔 보려고 만든 스위치 (10-9 focus·notice 규칙) */
export const mockProfile = {
  is_hypertension_diagnosed: true,
  is_diabetes_diagnosed: false,
  is_pregnant: false,
}
export function setMockProfile(p: Partial<typeof mockProfile>) {
  Object.assign(mockProfile, p)
}

// ─────────────────────────────────────────────
// foods (가짜 6행, id는 api.md 예시와 같음)
// ─────────────────────────────────────────────

const FOODS: Food[] = [
  { id: 14, name: '육개장', model_label: '육개장', serving_size: 420, serving_unit: 'G', kcal: 132.0, carbs_g: 6.6, sugar_g: 3.3, sodium_mg: 884.4, protein_g: 16.2, fat_g: 4.4 },
  { id: 6, name: '육개장_간편조리세트_닭개장', model_label: '닭개장', serving_size: 420, serving_unit: 'G', kcal: 172.2, carbs_g: null, sugar_g: 2.1, sodium_mg: 1503.6, protein_g: 15.0, fat_g: null },
  { id: 4, name: '김치찌개', model_label: '김치찌개', serving_size: 400, serving_unit: 'G', kcal: 244.0, carbs_g: 12.0, sugar_g: 4.0, sodium_mg: 1964.0, protein_g: 14.0, fat_g: 15.0 },
  { id: 13, name: '순두부찌개_해물', model_label: '순두부찌개', serving_size: 270, serving_unit: 'ML', kcal: 94.5, carbs_g: 6.0, sugar_g: 1.5, sodium_mg: 515.7, protein_g: 8.0, fat_g: 5.0 },
  { id: 3, name: '감자탕', model_label: '감자탕', serving_size: 650, serving_unit: 'ML', kcal: 175.5, carbs_g: 10.0, sugar_g: 2.0, sodium_mg: 708.5, protein_g: 12.0, fat_g: 9.0 },
  { id: 15, name: '잔치국수', model_label: '잔치국수', serving_size: 800, serving_unit: 'ML', kcal: 488.0, carbs_g: 84.6, sugar_g: 6.6, sodium_mg: 2176.0, protein_g: 19.2, fat_g: 6.7 },
]

const CANDIDATE_ORDER = [14, 6, 4, 13, 3] // 육개장 후보 5개 (api.md 10-4 예시)
const CANDIDATE_SCORES = [0.887, 0.061, 0.021, 0.012, 0.006]

function buildCandidates(order: number[] = CANDIDATE_ORDER): MealCandidate[] {
  return order.map((foodId, i) => {
    const f = FOODS.find((x) => x.id === foodId)!
    return {
      food_id: f.id,
      model_label: f.model_label,
      name: f.name,
      score: CANDIDATE_SCORES[i],
      serving_size: f.serving_size,
      serving_unit: f.serving_unit,
      kcal: f.kcal,
    }
  })
}

// ─────────────────────────────────────────────
// meals (메모리 저장. 새로고침하면 초기화)
// ─────────────────────────────────────────────

function pickFood(id: number, portion: Portion) {
  const f = FOODS.find((x) => x.id === id)!
  const nutrients = {} as Nutrients
  for (const k of NUTRIENT_KEYS) nutrients[k] = f[k] == null ? null : round1(f[k]! * portion)
  return {
    food: { id: f.id, name: f.name, model_label: f.model_label, serving_size: f.serving_size, serving_unit: f.serving_unit },
    portion,
    nutrients,
  }
}

function baseMeal(id: number, hhmm: string, status: MealDetail['status']): MealDetail {
  return {
    id,
    image_url: '', // 화면에서 빈 값이면 기본 이미지 자리 표시
    eaten_at: at(hhmm),
    category: 'MEAL',
    status,
    retry_count: 0,
    model_version: status === 'COMPLETED' ? 'food-cls-v1' : null,
    candidates: status === 'COMPLETED' ? buildCandidates() : null,
    food: null,
    portion: 1.0,
    nutrients: null,
    feedback: null,
    created_at: at(hhmm),
    updated_at: at(hhmm),
  }
}

function initialMeals(): MealDetail[] {
  return [
    // 아침: 육개장 1인분 골라 둔 상태 (10-9 예시의 "아침 식단")
    { ...baseMeal(100, '08:00', 'COMPLETED'), ...pickFood(14, 1.0) },
    // 점심: 분석 끝, 아직 안 고름 → S-22 확인용
    baseMeal(101, '12:30', 'COMPLETED'),
    // 오후: 닭개장 골라 둠 → 탄수화물·지방 null("정보 없음") 확인용
    { ...baseMeal(104, '15:00', 'COMPLETED'), candidates: buildCandidates([6, 14, 4, 13, 3]), ...pickFood(6, 1.0) },
    // 저녁: 분석 중
    baseMeal(102, '19:10', 'PROCESSING'),
    // 야식: 분석 실패 (재분석 1번 한 상태) → C-02 확인용
    { ...baseMeal(103, '21:00', 'FAILED'), retry_count: 1 },
  ]
}

let meals: MealDetail[] = initialMeals()
let nextId = 200
let taskSeq = 1

/** 가짜 데이터를 처음 상태로 되돌림 */
export function resetMock() {
  meals = initialMeals()
  nextId = 200
}

// ─────────────────────────────────────────────
// SSE 흉내 (공통 SSE 12-6 task 이벤트와 같은 모양)
// ─────────────────────────────────────────────

type TaskListener = (e: MealTaskEvent) => void
const listeners = new Set<TaskListener>()

/** 진짜 SSE 훅 대신 쓰는 구독 함수. 반환값은 해제 함수 */
export function subscribeMockTasks(cb: TaskListener): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

function finishClassify(mealId: number, taskId: string) {
  setTimeout(() => {
    const m = meals.find((x) => x.id === mealId)
    if (!m) return // 삭제됐으면 건너뜀 (워커와 같은 동작)
    m.status = 'COMPLETED'
    m.model_version = 'food-cls-v1'
    m.candidates = buildCandidates()
    listeners.forEach((cb) => cb({ task_id: taskId, task_type: 'MEAL_CLASSIFY', target_id: mealId, status: 'COMPLETED' }))
  }, 2000)
}

// ─────────────────────────────────────────────
// 피드백 계산 (10-9 규칙)
// ─────────────────────────────────────────────

function sortedPickedMeals(): MealDetail[] {
  return meals
    .filter((m) => m.food && m.nutrients)
    .sort((a, b) => (a.eaten_at < b.eaten_at ? -1 : a.eaten_at > b.eaten_at ? 1 : a.id - b.id))
}

function computeFeedback(meal: MealDetail): MealFeedback | null {
  if (!meal.food || !meal.nutrients) return null

  // 이 끼니까지 누적: eaten_at 이하 (같은 시각이면 id 순). 값이 null인 끼니는 0으로 더함
  const upTo = sortedPickedMeals().filter(
    (m) => m.eaten_at < meal.eaten_at || (m.eaten_at === meal.eaten_at && m.id <= meal.id),
  )

  const items: FeedbackItem[] = FEEDBACK_KEYS.map((key) => {
    const ref = DAILY_REFERENCE[key]
    const value = meal.nutrients![key]
    if (value == null) {
      return { key, meal_value: null, meal_percent: null, running_total: null, daily_reference: ref, percent: null, level: null }
    }
    const total = round1(upTo.reduce((sum, m) => sum + (m.nutrients![key] ?? 0), 0))
    const mealPercent = round1((value / ref) * 100)
    const percent = round1((total / ref) * 100)
    // 둘 다 해당하면 DAILY_OVER가 우선. 부족은 안내하지 않음
    const level: FeedbackLevel = percent > 100 ? 'DAILY_OVER' : mealPercent >= 33.3 ? 'MEAL_HIGH' : 'OK'
    return { key, meal_value: value, meal_percent: mealPercent, running_total: total, daily_reference: ref, percent, level }
  })

  let focus: FeedbackKey[] = []
  if (mockProfile.is_hypertension_diagnosed) focus.push('sodium_mg')
  if (mockProfile.is_diabetes_diagnosed) focus.push('sugar_g', 'carbs_g')
  let notice: string | null = null
  if (mockProfile.is_pregnant) {
    focus = []
    notice = '임신 중에는 의료진 안내를 따르세요.'
  }

  return { basis: '2,000kcal 기준 · 기록한 끼니 기준', focus, notice, items }
}

function withFeedback(meal: MealDetail): MealDetail {
  return { ...meal, feedback: computeFeedback(meal) }
}

// ─────────────────────────────────────────────
// meals.ts와 같은 이름의 함수들
// ─────────────────────────────────────────────

export async function uploadMeal(_image: File, eatenAt?: string): Promise<MealTaskResponse> {
  await wait()
  if (eatenAt && new Date(eatenAt).getTime() > Date.now()) {
    throw new MealApiError(400, '먹은 시간은 지금 이후로 할 수 없어요.')
  }
  const id = nextId++
  const m = baseMeal(id, '12:00', 'PENDING')
  if (eatenAt) m.eaten_at = eatenAt
  m.status = 'PROCESSING'
  meals.push(m)
  const taskId = `mock-task-${taskSeq++}`
  finishClassify(id, taskId)
  return { meal_id: id, task_id: taskId, status: 'PENDING' }
}

export async function retryMeal(id: number): Promise<MealTaskResponse> {
  await wait()
  const m = meals.find((x) => x.id === id)
  if (!m) throw new MealApiError(404, '식단을 찾을 수 없어요.')
  if (m.status !== 'FAILED') throw new MealApiError(409, '다시 분석할 수 없는 상태예요.')
  if (m.retry_count >= 3) throw new MealApiError(429, '분석은 3번까지 할 수 있어요. 직접 골라 주세요.')
  m.status = 'PROCESSING'
  const taskId = `mock-task-${taskSeq++}`
  finishClassify(id, taskId)
  return { meal_id: id, task_id: taskId, status: 'PENDING' }
}

export async function listMeals(date: string): Promise<MealListResponse> {
  await wait()
  const picked = date === MOCK_DATE ? sortedPickedMeals() : []
  const items: MealListItem[] =
    date === MOCK_DATE
      ? [...meals]
          .sort((a, b) => (a.eaten_at < b.eaten_at ? -1 : a.eaten_at > b.eaten_at ? 1 : a.id - b.id))
          .map((m) => ({
            id: m.id,
            image_url: m.image_url,
            eaten_at: m.eaten_at,
            status: m.status,
            food: m.food ? { id: m.food.id, name: m.food.name } : null,
            portion: m.portion,
            nutrients: m.nutrients,
          }))
      : []
  const daily_total = {} as Nutrients
  for (const k of NUTRIENT_KEYS) daily_total[k] = round1(picked.reduce((s, m) => s + (m.nutrients![k] ?? 0), 0))
  return clone({ date, items, daily_total })
}

export async function getMeal(id: number): Promise<MealDetail> {
  await wait()
  const m = meals.find((x) => x.id === id)
  if (!m) throw new MealApiError(404, '식단을 찾을 수 없어요.')
  return clone(withFeedback(m))
}

export async function updateMeal(id: number, body: UpdateMealBody): Promise<MealDetail> {
  await wait()
  const m = meals.find((x) => x.id === id)
  if (!m) throw new MealApiError(404, '식단을 찾을 수 없어요.')
  if (m.status === 'PENDING' || m.status === 'PROCESSING') {
    throw new MealApiError(409, '사진을 분석하고 있어요. 잠시 후 골라 주세요.')
  }
  if (body.portion !== undefined && ![0.5, 1.0, 1.5].includes(body.portion)) {
    throw new MealApiError(422, 'portion은 0.5 / 1.0 / 1.5만 가능해요.')
  }
  if (body.eaten_at && new Date(body.eaten_at).getTime() > Date.now()) {
    throw new MealApiError(400, '먹은 시간은 지금 이후로 할 수 없어요.')
  }
  if (body.food_id === undefined && body.portion !== undefined && !m.food) {
    throw new MealApiError(400, '음식을 먼저 골라 주세요.')
  }
  if (body.food_id !== undefined && !FOODS.some((f) => f.id === body.food_id)) {
    throw new MealApiError(404, '음식을 찾을 수 없어요.')
  }

  if (body.eaten_at) m.eaten_at = body.eaten_at
  const foodId = body.food_id ?? m.food?.id
  const portion = (body.portion ?? m.portion) as Portion
  if (foodId !== undefined) Object.assign(m, pickFood(foodId, portion)) // 고를 때 값을 스냅샷으로 저장
  return clone(withFeedback(m))
}

export async function deleteMeal(id: number): Promise<void> {
  await wait()
  meals = meals.filter((m) => m.id !== id)
}

export async function listFoods(q?: string): Promise<Food[]> {
  await wait()
  const keyword = q?.trim()
  const items = keyword ? FOODS.filter((f) => f.name.includes(keyword) || f.model_label.includes(keyword)) : FOODS
  return clone(items)
}
