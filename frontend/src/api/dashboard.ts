// frontend/src/api/dashboard.ts
// 7장 대시보드 중 기록 탭(S-19)이 쓰는 두 개
//  - 7-1 위험도 추이: 질환별로 주마다 마지막 예측 1개 (예측이 없는 주는 점이 빠짐)
//  - 7-2 항목별 그래프: bucket=day면 서버가 하루 평균으로 묶어 줌 (혈압은 수축기·이완기 각각)

import type { Disease, RiskLevel } from './predictions'
import type { DailyLogType } from './healthLogs'
import { apiFetch, toApiError } from './client'

export interface TrendPoint {
  week_start: string // 그 주 월요일 (KST)
  score: number
  level: RiskLevel
  prediction_id: number // 5-3 상세(바뀐 응답)를 볼 때 씀
  criteria_level: RiskLevel | null
}

export interface TrendSeries {
  disease: Disease
  managed: boolean // 진단받은 질환 → 추이 대신 관리 중
  points: TrendPoint[]
}

export interface DayPoint {
  date: string // "2026-11-18"
  value: number // 그날 평균
  value2: number | null // 혈압 이완기 평균
  count: number
}

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

/** 7-1. 설문 전이어도 두 질환이 빈 points로 옴 */
export async function getRiskTrend(weeks: number, signal?: AbortSignal): Promise<TrendSeries[]> {
  if (useMock) return [] // 가짜 모드에선 추이 카드를 숨김
  const res = await apiFetch(`/dashboard/risk-trend?weeks=${weeks}`, { signal, cache: 'no-store' })
  if (!res.ok) throw await toApiError(res)
  return ((await res.json()) as { series: TrendSeries[] }).series
}

/** 7-2 bucket=day: 기록이 있는 날만 점 (없는 날은 빠짐) */
export async function getDailyPoints(logType: DailyLogType, from: string, to: string, signal?: AbortSignal): Promise<DayPoint[]> {
  if (useMock) return []
  const query = new URLSearchParams({ log_type: logType, from, to, bucket: 'day' })
  const res = await apiFetch(`/dashboard/logs?${query}`, { signal, cache: 'no-store' })
  if (!res.ok) throw await toApiError(res)
  return ((await res.json()) as { points: DayPoint[] }).points
}
