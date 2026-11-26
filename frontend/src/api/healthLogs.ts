// frontend/src/api/healthLogs.ts
// 6장 건강 기록 (api.md 6-0~6-2)
//  - 홈(S-12) 컨디션: 좋음 2 · 보통 1 · 나쁨 0, 같은 날(KST) 다시 저장하면 서버가 덮어씀
//  - 기록 탭(S-19): 일일 기록 6종 조회·저장 (값 범위·소수점은 서버가 검사하고 400 문구를 줌)

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

/** 기록 탭에서 쓰는 일일 기록 종류 (api.md 6-0 위쪽, 컨디션 제외) */
export type DailyLogType = 'BLOOD_PRESSURE' | 'BLOOD_GLUCOSE' | 'WEIGHT' | 'STEPS' | 'EXERCISE' | 'ALCOHOL'

/** 6-2 응답 한 행 */
export interface HealthLog {
  id: number
  log_type: DailyLogType
  value: number
  value2: number | null // 혈압 이완기만
  unit: string | null
  measured_at: string // ISO, +09:00
  memo: string | null
}

export interface NewHealthLog {
  log_type: DailyLogType
  value: number
  value2?: number
  measured_at: string // "2026-11-19T07:40" (시간대 없으면 서버가 KST로 봄)
}

// 가짜 모드: 저장한 값을 메모리에만 둠 (새로고침하면 사라짐)
const mockLogs: HealthLog[] = []

/** 6-2: 기간(KST 날짜, 양끝 포함) 안의 기록, measured_at 오름차순 */
export async function listHealthLogs(logType: DailyLogType, from: string, to: string, signal?: AbortSignal): Promise<HealthLog[]> {
  if (useMock) return mockLogs.filter((log) => log.log_type === logType)
  const query = new URLSearchParams({ log_type: logType, from, to })
  const res = await apiFetch(`/health-logs?${query}`, { signal, cache: 'no-store' })
  if (!res.ok) throw await toApiError(res)
  return ((await res.json()) as { items: HealthLog[] }).items
}

/** 6-1 저장. 걸음 수는 같은 날이면 서버가 덮어씀(200). 범위 밖 등은 ApiError(400, 서버 문구) */
export async function createHealthLog(body: NewHealthLog): Promise<void> {
  if (useMock) {
    mockLogs.push({ id: mockLogs.length + 1, value2: null, unit: null, memo: null, ...body, measured_at: `${body.measured_at}:00+09:00` })
    return
  }
  const res = await apiFetch('/health-logs', { method: 'POST', body: JSON.stringify(body) })
  if (!res.ok) throw await toApiError(res)
}
