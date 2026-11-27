// frontend/src/records/recordView.ts
// 기록 탭 화면 규칙 (DB·화면 없이 테스트하는 순수 함수): 조회 기간, 그래프 좌표, 날짜 문구, 입력 기본 시각

import { dateInSeoul } from '../api/challenges'

export const CHART_DAYS = 14 // Figma M07 "최근 2주"

/** 그래프·목록 조회 기간: 오늘 포함 최근 14일 (KST 날짜, 양끝 포함 → api.md 6-2) */
export function recentRange(): { from: string; to: string } {
  return { from: dateInSeoul(-(CHART_DAYS - 1)), to: dateInSeoul() }
}

/** 그래프 점 하나: x는 0~1 (기간 안의 위치), y는 값 */
export interface ChartPoint {
  x: number
  y: number
}

/**
 * 값 여러 줄(혈압은 수축기·이완기 2줄)을 같은 눈금으로 SVG 좌표 문자열로 바꿈. 큰 값이 위.
 * x는 날짜 위치라서 빠진 날은 간격이 벌어짐 (#139 현영 님 리뷰). 위아래 값이 같으면 가운데.
 */
export function chartLines(series: ChartPoint[][], width: number, height: number, pad = 8): string[] {
  const ys = series.flat().map((point) => point.y)
  if (ys.length === 0) return series.map(() => '')
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const toY = (v: number) => (max === min ? height / 2 : pad + ((max - v) / (max - min)) * (height - pad * 2))
  const round = (v: number) => Math.round(v * 10) / 10
  return series.map((points) =>
    points.map((point) => `${round(pad + point.x * (width - pad * 2))},${round(toY(point.y))}`).join(' '),
  )
}

/** "2026-11-18"이 기간 시작일(from)에서 며칠째인지 → 0~1 (CHART_DAYS 기준) */
export function dayPosition(date: string, from: string): number {
  const days = (Date.parse(date) - Date.parse(from)) / 86_400_000
  return Math.min(1, Math.max(0, days / (CHART_DAYS - 1)))
}

/** "2026-11-19T07:40:00+09:00" → "11월 19일 07:40" (서울 기준) */
export function logTimeLabel(measuredAt: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(measuredAt))
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${get('month')}월 ${get('day')}일 ${get('hour')}:${get('minute')}`
}

/** datetime-local 입력칸 기본값·최댓값: 지금(서울) "2026-11-19T07:40" — 서버는 시간대 없는 값을 KST로 봄 (api.md 6-1) */
export function nowInSeoulInput(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`
}
