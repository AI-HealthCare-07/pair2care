// frontend/src/home/homeView.ts
// 홈(S-12, Figma M05) 화면 규칙. 화면 컴포넌트는 이 결과만 보고 그림

import type { Disease, LatestPrediction, LatestPredictionsResponse, RiskLevel } from '../api/predictions'
import { healthAgeLine, type HealthAgeLine } from '../prediction/healthAge'

const LEVEL_RANK: Record<RiskLevel, number> = { LOW: 0, CAUTION: 1, HIGH: 2 }
// 단계·점수가 같으면 당뇨 먼저 (서버 7-3 priority_disease와 같은 순서)
const DISEASE_RANK: Record<Disease, number> = { DIABETES: 0, HYPERTENSION: 1 }

export interface HomeHealthAge {
  disease: Disease
  line: HealthAgeLine
}

/**
 * 홈 건강 나이는 "높은 쪽 하나"만 (11/25 결정): 단계 높은 쪽 → 점수 높은 쪽 → 당뇨.
 * 진단받은 질환은 MODEL 행이 없어서 자연히 빠짐 (7-3 priority_disease는 관리 중 우선이라 그대로 못 씀, #108 리뷰).
 * 건강 나이가 null인 행은 후보에서 빼고, 하나도 없으면 null → 카드 숨김
 */
export function pickHomeHealthAge(latest: LatestPredictionsResponse): HomeHealthAge | null {
  const candidates = latest.predictions.filter(
    (p): p is LatestPrediction & { score: number } => p.method === 'MODEL' && p.score !== null && healthAgeLine(p.health_age) !== null,
  )
  candidates.sort(
    (a, b) =>
      LEVEL_RANK[b.level] - LEVEL_RANK[a.level] || b.score - a.score || DISEASE_RANK[a.disease] - DISEASE_RANK[b.disease],
  )
  const top = candidates[0]
  const line = top ? healthAgeLine(top.health_age) : null
  return top && line ? { disease: top.disease, line } : null
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

/** "11월 25일 수요일" (서울 기준 날짜) */
export function homeDateLabel(now: Date): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
  }).formatToParts(now)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  const weekday = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(get('weekday'))
  return `${get('month')}월 ${get('day')}일 ${WEEKDAYS[weekday]}요일`
}

/** 추천 본문의 [1] 같은 번호가 실제 출처 배열에 있는 것만 (서버도 맞추지만, 없는 번호를 링크로 만들지 않게) */
export function usedSources<T extends { number: number }>(content: string, sources: T[]): T[] {
  const cited = new Set([...content.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])))
  return sources.filter((s) => cited.has(s.number))
}
