// frontend/src/api/recommendationFeedback.ts
// 11-9 추천 피드백 (REQ-NFR-019). 추천당 1개, 다시 보내면 덮어씀 → PUT

import { apiFetch, toApiError } from './client'
import type { DailyRecommendation, FeedbackReason, MyFeedback } from './recommendations'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

export const FEEDBACK_REASONS: { value: FeedbackReason; label: string }[] = [
  { value: 'NOT_FIT', label: '나한테 안 맞아요' },
  { value: 'ALREADY_DOING', label: '이미 하고 있어요' },
  { value: 'TOO_HARD', label: '너무 어려워요' },
  { value: 'WRONG_CONTENT', label: '내용이 이상해요' },
  { value: 'OTHER', label: '기타' },
]

/** 완료됐고 근거가 있는 추천에만 버튼을 보임 (근거 부족이면 서버도 409) */
export function canGiveFeedback(rec: Pick<DailyRecommendation, 'status' | 'sources'>): boolean {
  return rec.status === 'COMPLETED' && (rec.sources?.length ?? 0) > 0
}

/** 11-9 PUT. 도움 돼요면 reason을 안 보냄(서버가 지움). 400·404·409는 ApiError(서버 문구) */
export async function saveFeedback(recommendationId: number, feedback: MyFeedback): Promise<MyFeedback> {
  const body = feedback.is_helpful ? { is_helpful: true } : { is_helpful: false, reason: feedback.reason }
  if (useMock) return { is_helpful: feedback.is_helpful, reason: feedback.is_helpful ? null : feedback.reason }
  const res = await apiFetch(`/recommendations/${recommendationId}/feedback`, { method: 'PUT', body: JSON.stringify(body) })
  if (!res.ok) throw await toApiError(res)
  const saved = (await res.json()) as MyFeedback
  return { is_helpful: saved.is_helpful, reason: saved.reason }
}
