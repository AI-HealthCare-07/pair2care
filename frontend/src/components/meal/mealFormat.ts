// frontend/src/components/meal/mealFormat.ts
// S-22·S-23에서 같이 쓰는 표시용 포맷 함수

import type { Portion, ServingUnit } from '../../api/meals'

/** 인분 선택지 (api.md 10-5: 0.5 / 1.0 / 1.5만 허용) */
export const PORTIONS: Portion[] = [0.5, 1.0, 1.5]

/** 0.5 → '0.5인분', 1 → '1인분' */
export function portionLabel(p: number): string {
  return `${p}인분`
}

/** '1인분 515mL · 499kcal'. kcal이 null이면 '1인분 515mL'만 */
export function servingText(size: number, unit: ServingUnit, kcal: number | null): string {
  const u = unit === 'ML' ? 'mL' : 'g'
  const base = `1인분 ${Math.round(size).toLocaleString('ko-KR')}${u}`
  return kcal == null ? base : `${base} · ${Math.round(kcal)}kcal`
}
