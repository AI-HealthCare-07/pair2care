// frontend/src/api/recommendations.ts
// 11-1·11-2 오늘의 한 가지 (DAILY_ACTION). 저장본 조회(GET)가 먼저, 없을 때만 생성(POST) → 워커가 채움
// 완료 알림 SSE(12-6)가 아직 없어서 화면은 PENDING·PROCESSING이면 GET을 다시 불러 확인함

import { apiFetch, ApiError, toApiError } from './client'

export type RecommendationStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

export interface RecommendationSource {
  number: number // 본문의 [1]과 같은 번호
  title: string
  url: string
}

/** 11-5 저장 추천 공통 형식 (화면에서 쓰는 필드만) */
export interface DailyRecommendation {
  id: number
  status: RecommendationStatus
  content: string | null // PENDING·PROCESSING·FAILED면 null
  sources: RecommendationSource[] | null
  retry_count: number // 3이면 다시 요청해도 429
  target_on: string
  my_feedback?: MyFeedback | null // 11-9에 남긴 피드백, 없으면 null
}

/** 11-9 별로예요 이유 (선택) */
export type FeedbackReason = 'NOT_FIT' | 'ALREADY_DOING' | 'TOO_HARD' | 'WRONG_CONTENT' | 'OTHER'

export interface MyFeedback {
  is_helpful: boolean
  reason: FeedbackReason | null
}

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

const MOCK_DAILY: DailyRecommendation = {
  id: 1,
  status: 'COMPLETED',
  content: '점심 먹고 엘리베이터 대신 계단으로 2층만 올라가 볼까요? [1]',
  sources: [{ number: 1, title: '질병관리청 신체활동 지침(예시)', url: 'https://example.com/activity-guide' }],
  retry_count: 0,
  target_on: '2026-11-25',
}

/** 11-2. 오늘 저장본이 없으면(404) null → 화면이 11-1로 생성 요청 */
export async function getDailyRecommendation(signal?: AbortSignal): Promise<DailyRecommendation | null> {
  if (useMock) return MOCK_DAILY
  const res = await apiFetch('/recommendations/daily', { signal, cache: 'no-store' })
  if (res.status === 404) return null
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as DailyRecommendation
}

/** 11-1. 202(새 작업)·200(이미 있음) 둘 다 성공 → 결과는 11-2로 다시 읽음. 429(횟수 다 씀)·503(큐 실패)은 ApiError */
export async function requestDailyRecommendation(): Promise<void> {
  if (useMock) return
  const res = await apiFetch('/recommendations/daily', { method: 'POST' })
  if (!res.ok) throw await toApiError(res)
}

export function isRetryLimit(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429
}
