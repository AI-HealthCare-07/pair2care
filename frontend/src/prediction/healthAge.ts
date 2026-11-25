// frontend/src/prediction/healthAge.ts
// 건강 나이 한 줄 (api.md 5-2 health_age, 팀장님 11/25 문구 규칙)
//  - 실제 나이와 같은 10살 구간이면 "비슷한 수준", 다를 때만 "높게 / 낮게"
//  - 곡선 밖: BELOW "30세 미만 수준" / ABOVE "69세 초과 수준" (#102 리뷰에서 맞춤)
//    실제 나이는 항상 30~69세라 BELOW는 늘 "낮게", ABOVE는 늘 "높게"
//  - health_age가 null이면 줄 숨김

import type { HealthAge } from '../api/predictions'

export type HealthAgeCompare = 'SIMILAR' | 'HIGHER' | 'LOWER'

export interface HealthAgeLine {
  level: string // "50대 수준" · "30세 미만 수준" · "69세 초과 수준"
  compare: HealthAgeCompare
  compareText: string
}

const COMPARE_TEXT: Record<HealthAgeCompare, string> = {
  SIMILAR: '실제 나이와 비슷한 수준이에요',
  HIGHER: '실제 나이보다 높게 나왔어요',
  LOWER: '실제 나이보다 낮게 나왔어요',
}

/** 만 나이 → 10살 구간 (45 → 40) */
export function decadeOf(age: number): number {
  return Math.floor(age / 10) * 10
}

/** null이면 화면에서 건강 나이 줄을 숨김 */
export function healthAgeLine(healthAge: HealthAge | null): HealthAgeLine | null {
  if (!healthAge) return null

  let level: string
  let compare: HealthAgeCompare
  if (healthAge.out_of_range === 'BELOW') {
    level = '30세 미만 수준'
    compare = 'LOWER'
  } else if (healthAge.out_of_range === 'ABOVE') {
    level = '69세 초과 수준'
    compare = 'HIGHER'
  } else if (healthAge.decade !== null) {
    level = `${healthAge.decade}대 수준`
    const actual = decadeOf(healthAge.actual_age)
    compare = healthAge.decade === actual ? 'SIMILAR' : healthAge.decade > actual ? 'HIGHER' : 'LOWER'
  } else {
    return null // decade·out_of_range 둘 다 없음 (서버 규칙상 안 나옴) → 숨김
  }
  return { level, compare, compareText: COMPARE_TEXT[compare] }
}
