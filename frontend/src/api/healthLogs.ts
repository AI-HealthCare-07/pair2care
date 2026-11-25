// frontend/src/api/healthLogs.ts
// 6장 건강 기록 중 홈(S-12)이 쓰는 컨디션만. 좋음 2 · 보통 1 · 나쁨 0, 같은 날(KST) 다시 저장하면 서버가 덮어씀 (api.md 6-0·6-1)

import { apiFetch, toApiError } from './client'
import { dateInSeoul } from './challenges'

export type ConditionValue = 0 | 1 | 2

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
let mockCondition: ConditionValue | null = null

function toCondition(value: unknown): ConditionValue | null {
  return value === 0 || value === 1 || value === 2 ? value : null
}

/** 6-2로 오늘(KST) 컨디션 읽기. 기록이 없으면 null */
export async function getTodayCondition(signal?: AbortSignal): Promise<ConditionValue | null> {
  if (useMock) return mockCondition
  const today = dateInSeoul()
  const query = new URLSearchParams({ log_type: 'CONDITION', from: today, to: today })
  const res = await apiFetch(`/health-logs?${query}`, { signal, cache: 'no-store' })
  if (!res.ok) throw await toApiError(res)
  const body = (await res.json()) as { items: { value: unknown }[] }
  return toCondition(body.items.at(-1)?.value) // 하루 1행이지만 혹시 여러 개면 마지막
}

/** 6-1 저장 (200 덮어씀 · 201 새로 둘 다 성공). measured_at은 생략 → 서버가 지금 시각 */
export async function saveCondition(value: ConditionValue): Promise<void> {
  if (useMock) {
    mockCondition = value
    return
  }
  const res = await apiFetch('/health-logs', { method: 'POST', body: JSON.stringify({ log_type: 'CONDITION', value }) })
  if (!res.ok) throw await toApiError(res)
}
