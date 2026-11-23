// frontend/src/api/meals.ts
// api.md 10장 (식단 — meals, foods) 기준. 필드명은 서버 응답 그대로 snake_case.
import { apiFetch } from './client'

// ─────────────────────────────────────────────
// 공통 타입
// ─────────────────────────────────────────────

export type MealStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
export type MealCategory = 'MEAL' // 1차는 식사만
export type ServingUnit = 'G' | 'ML'
export type Portion = 0.5 | 1.0 | 1.5

/** 영양값. 식약처 값이 없는 항목은 null → 화면은 "정보 없음" (예: 닭개장 탄수화물·지방) */
export interface Nutrients {
  kcal: number | null
  carbs_g: number | null
  sugar_g: number | null
  sodium_mg: number | null
  protein_g: number | null
  fat_g: number | null
}

/** 서버 에러 본문 (503·429·409·400 등 공통) */
export interface ApiErrorBody {
  detail: string
}

/**
 * apiFetch는 4xx/5xx여도 throw하지 않고 Response를 돌려줌 → 여기서 에러로 바꿈.
 * 화면은 status로 분기 (503 큐 실패 · 429 3번 초과 · 409 분석 중/상태 아님 · 413 크기 초과 등)
 */
export class MealApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'MealApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, options)
  if (!res.ok) {
    let detail = '요청을 처리하지 못했어요.'
    try {
      const body = (await res.json()) as Partial<ApiErrorBody>
      // 422(검증 오류)는 detail이 배열일 수 있어서 문자열일 때만 사용
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // 본문이 JSON이 아니면 기본 문구
    }
    throw new MealApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ─────────────────────────────────────────────
// 10-1 · 10-6 사진 올리기 / 다시 분류
// ─────────────────────────────────────────────

export interface MealTaskResponse {
  meal_id: number
  task_id: string
  status: 'PENDING'
}

/** 10-1 POST /meals (multipart). 202 + task_id. 503이면 task_id 없음 → SSE 기다리지 않음 */
export async function uploadMeal(image: File, eatenAt?: string): Promise<MealTaskResponse> {
  const form = new FormData()
  form.append('image', image)
  if (eatenAt) form.append('eaten_at', eatenAt)
  // apiFetch가 FormData면 Content-Type을 건드리지 않음 (boundary는 브라우저가 붙임)
  return request<MealTaskResponse>('/meals', { method: 'POST', body: form })
}

/** 10-6 POST /meals/{id}/retry. FAILED일 때만. 409(상태 아님) · 429(3번 초과) · 503(큐 실패) */
export async function retryMeal(id: number): Promise<MealTaskResponse> {
  return request<MealTaskResponse>(`/meals/${id}/retry`, { method: 'POST' })
}

// ─────────────────────────────────────────────
// 10-2 분류 결과 알림 (공통 SSE 12-6의 task 이벤트)
// ─────────────────────────────────────────────

/** SSE는 공통 훅에서 받음. 식단 화면은 task_type === 'MEAL_CLASSIFY'만 처리 */
export interface MealTaskEvent {
  task_id: string
  task_type: 'MEAL_CLASSIFY'
  target_id: number // meals.id
  status: 'COMPLETED' | 'FAILED'
}

// ─────────────────────────────────────────────
// 10-3 하루 식단 목록
// ─────────────────────────────────────────────

export interface FoodRef {
  id: number
  name: string
}

export interface MealListItem {
  id: number
  image_url: string
  eaten_at: string // ISO 8601, +09:00
  status: MealStatus
  food: FoodRef | null
  portion: Portion
  nutrients: Nutrients | null
}

export interface MealListResponse {
  date: string // YYYY-MM-DD (KST)
  items: MealListItem[]
  daily_total: Nutrients // 음식을 고른 식단 전체 합 (하루 요약용, level 없음)
}

/** 10-3 GET /meals?date=YYYY-MM-DD. eaten_at 순, 커서 없음 */
export async function listMeals(date: string): Promise<MealListResponse> {
  return request<MealListResponse>(`/meals?date=${encodeURIComponent(date)}`)
}

// ─────────────────────────────────────────────
// 10-4 식단 한 건 / 10-5 고르기
// ─────────────────────────────────────────────

/** 후보마다 foods의 1인분 값이 붙어서 옴 → "1인분 797mL · 390kcal" 표시용 */
export interface MealCandidate {
  food_id: number
  model_label: string
  name: string
  score: number // 0~1, 소수 셋째 자리
  serving_size: number
  serving_unit: ServingUnit
  kcal: number | null
}

/** 고른 음식 요약 (고르기 전엔 meal.food === null) */
export interface MealFood {
  id: number
  name: string
  model_label: string
  serving_size: number
  serving_unit: ServingUnit
}

export type FeedbackKey = 'sodium_mg' | 'sugar_g' | 'carbs_g'
export type FeedbackLevel = 'OK' | 'MEAL_HIGH' | 'DAILY_OVER'

export interface FeedbackItem {
  key: FeedbackKey
  // 해당 영양값이 null이면 아래 값은 모두 null (level 포함)
  meal_value: number | null
  meal_percent: number | null // 이 끼니 ÷ 하루 기준치 × 100
  running_total: number | null // 이 끼니까지 누적
  daily_reference: number
  percent: number | null // running_total ÷ 하루 기준치 × 100
  level: FeedbackLevel | null
}

export interface MealFeedback {
  basis: string // "2,000kcal 기준 · 기록한 끼니 기준"
  focus: FeedbackKey[] // 설문 진단 "예"만. 진단 없으면 []
  notice: string | null // 임신 중이면 안내 문구 (focus는 [])
  items: FeedbackItem[]
}

export interface MealDetail {
  id: number
  image_url: string
  eaten_at: string
  category: MealCategory
  status: MealStatus
  retry_count: number
  model_version: string | null
  candidates: MealCandidate[] | null // COMPLETED일 때만 5개, 그 전·FAILED면 null
  food: MealFood | null
  portion: Portion
  nutrients: Nutrients | null
  feedback: MealFeedback | null // 음식을 고른 뒤에만
  created_at: string
  updated_at: string
}

/** 10-4 GET /meals/{id} */
export async function getMeal(id: number): Promise<MealDetail> {
  return request<MealDetail>(`/meals/${id}`)
}

/** 10-5 요청 본문. 보낸 필드만 바뀜 */
export interface UpdateMealBody {
  food_id?: number
  portion?: Portion
  eaten_at?: string
}

/**
 * 10-5 PATCH /meals/{id}. 응답은 10-4와 같은 형식 (food·nutrients·feedback 채워짐)
 * 400(음식 먼저) · 404(food_id 없음) · 409(분석 중) · 422(portion 값)
 */
export async function updateMeal(id: number, body: UpdateMealBody): Promise<MealDetail> {
  return request<MealDetail>(`/meals/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

// ─────────────────────────────────────────────
// 10-7 삭제
// ─────────────────────────────────────────────

/** 10-7 DELETE /meals/{id} → 204. 분석 중에도 가능 */
export async function deleteMeal(id: number): Promise<void> {
  await request<void>(`/meals/${id}`, { method: 'DELETE' })
}

// ─────────────────────────────────────────────
// 10-8 음식 목록·검색
// ─────────────────────────────────────────────

export interface Food {
  id: number
  name: string
  model_label: string
  serving_size: number
  serving_unit: ServingUnit
  kcal: number | null
  carbs_g: number | null
  sugar_g: number | null
  sodium_mg: number | null
  protein_g: number | null
  fat_g: number | null
}

/** 10-8 GET /foods?q=. q 없으면 18행 전부, 있으면 name·model_label 부분 일치 */
export async function listFoods(q?: string): Promise<Food[]> {
  const query = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await request<{ items: Food[] }>(`/foods${query}`)
  return data.items
}
