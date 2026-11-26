// frontend/src/records/recordView.ts
// 기록 탭 화면 규칙 (DB·화면 없이 테스트하는 순수 함수): 조회 기간, 그래프 좌표, 날짜 문구, 입력 기본 시각

import { dateInSeoul } from '../api/challenges'

export const CHART_DAYS = 14 // Figma M07 "최근 2주"

/** 그래프·목록 조회 기간: 오늘 포함 최근 14일 (KST 날짜, 양끝 포함 → api.md 6-2) */
export function recentRange(): { from: string; to: string } {
  return { from: dateInSeoul(-(CHART_DAYS - 1)), to: dateInSeoul() }
}

/**
 * 값 여러 줄(혈압은 수축기·이완기 2줄)을 같은 눈금으로 SVG 좌표로 바꿈.
 * 위아래 값이 같으면(기록 1개 등) 가운데에 그림. 점이 1개면 가운데 x.
 */
export function chartLines(series: number[][], width: number, height: number, pad = 8): string[] {
  const all = series.flat()
  if (all.length === 0) return series.map(() => '')
  const min = Math.min(...all)
  const max = Math.max(...all)
  const y = (v: number) => (max === min ? height / 2 : pad + ((max - v) / (max - min)) * (height - pad * 2))
  return series.map((values) =>
    values
      .map((v, i) => {
        const x = values.length === 1 ? width / 2 : pad + (i / (values.length - 1)) * (width - pad * 2)
        return `${Math.round(x * 10) / 10},${Math.round(y(v) * 10) / 10}`
      })
      .join(' '),
  )
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
