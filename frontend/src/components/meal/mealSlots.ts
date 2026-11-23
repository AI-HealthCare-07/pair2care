// frontend/src/components/meal/mealSlots.ts
// S-21(기록 > 식단 탭)에서 쓰는 끼니 구분·날짜·행 요약 유틸

import type { MealListItem } from '../../api/meals'

/** 하루 기준 열량 (api.md 10-9: 2,000kcal 기준, 모두 같은 값) */
export const DAILY_KCAL = 2000

export type Slot = '아침' | '점심' | '저녁'
const SLOTS: Slot[] = ['아침', '점심', '저녁']

/**
 * 먹은 시각으로 끼니 이름을 붙임. API에는 끼니 구분이 없어서 화면에서만 쓰는 표시용 규칙.
 * eaten_at은 서버가 +09:00(KST)로 주므로 문자열의 시(hour)를 그대로 읽음.
 */
export function slotOf(eatenAt: string): Slot {
  const hour = Number(eatenAt.slice(11, 13))
  if (hour < 11) return '아침'
  if (hour < 16) return '점심'
  return '저녁'
}

/** 기록이 하나도 없는 끼니 중 가장 이른 것 (점선 "+ 기록" 칸용). 셋 다 있으면 null */
export function firstEmptySlot(items: MealListItem[]): Slot | null {
  const used = new Set(items.map((i) => slotOf(i.eaten_at)))
  return SLOTS.find((s) => !used.has(s)) ?? null
}

/** 오늘 날짜(KST) YYYY-MM-DD */
export function todayKst(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date())
}

/** '2026-11-19' → '11월 19일' */
export function formatMonthDay(date: string): string {
  const [, m, d] = date.split('-')
  return `${Number(m)}월 ${Number(d)}일`
}

/**
 * S-23(영양 결과, /records/meals/:id/result)이 아직 없음 → false인 동안은 결과 화면 대신
 * 목록·고르기 화면으로 보냄 (404 방지). S-23 PR에서 true로 바꾸면 결과 화면으로 이동.
 */
export const RESULT_PAGE_READY = false

/** 음식을 저장한 직후 이동할 곳: S-23이 있으면 결과, 없으면 목록 */
export function afterSavePath(mealId: number): string {
  return RESULT_PAGE_READY ? `/records/meals/${mealId}/result` : '/records/meals'
}

/** 행을 눌렀을 때 이동할 곳: 음식을 골랐고 S-23이 있으면 결과, 아니면 고르기(S-22, 고른 음식이 선택된 채 열림) */
export function mealRoute(item: MealListItem): string {
  return RESULT_PAGE_READY && item.status === 'COMPLETED' && item.food
    ? `/records/meals/${item.id}/result`
    : `/records/meals/${item.id}`
}

export interface RowSummary {
  title: string
  /** 음식을 고른 행만 true. kcal이 null이면 "정보 없음" 표시 */
  picked: boolean
  kcal: number | null
}

export function rowSummary(item: MealListItem): RowSummary {
  if (item.food) {
    return {
      title: `${item.food.name} ${item.portion}인분`,
      picked: true,
      kcal: item.nutrients?.kcal ?? null,
    }
  }
  if (item.status === 'PENDING' || item.status === 'PROCESSING') {
    return { title: '사진을 분석하고 있어요', picked: false, kcal: null }
  }
  if (item.status === 'FAILED') {
    return { title: '분석하지 못했어요. 직접 골라 주세요', picked: false, kcal: null }
  }
  return { title: '음식을 골라 주세요', picked: false, kcal: null }
}