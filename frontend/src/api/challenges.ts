import { apiFetch } from './client'

export class RequestError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function requireSuccess(response: Response, fallback: string): Promise<void> {
  if (response.ok) return
  const payload = await response.json().catch(() => null)
  throw new RequestError(response.status, typeof payload?.detail === 'string' ? payload.detail : fallback)
}

export function dateInSeoul(offset = 0): string {
  const seoulDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = (type: string) => Number(seoulDay.find((part) => part.type === type)?.value)
  return new Date(Date.UTC(value('year'), value('month') - 1, value('day') + offset)).toISOString().slice(0, 10)
}

export const isChallengeDemo = import.meta.env.VITE_USE_MOCK === 'true'

export interface Challenge {
  id: number
  title: string
  status: 'ACTIVE' | 'ENDED'
  my_status: 'JOINED' | 'INVITED' | 'LEFT'
  this_week: { checked: number; target: number }
  checked_today: boolean
  decision_required: boolean
}

const demoChallenges: Challenge[] = isChallengeDemo ? [
  { id: 1, title: '점심 후 10분 걷기', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 2, target: 3 }, checked_today: false, decision_required: false },
  { id: 2, title: '물 6잔 마시기', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 3, target: 7 }, checked_today: false, decision_required: false },
  { id: 3, title: '단 음료 대신 아메리카노', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 1, target: 3 }, checked_today: false, decision_required: false },
] : []

export async function listChallenges(signal: AbortSignal): Promise<Challenge[]> {
  if (isChallengeDemo) return [...demoChallenges]
  const response = await apiFetch('/challenges?status=ACTIVE', { signal })
  await requireSuccess(response, '오늘의 챌린지를 불러오지 못했어요.')
  const payload: { items: Challenge[] } = await response.json()
  return payload.items.filter(({ status, my_status }) => status === 'ACTIVE' && my_status === 'JOINED')
}

export async function readChallenge(id: number, signal: AbortSignal) {
  if (isChallengeDemo) {
    const challenge = demoChallenges.find((item) => item.id === id)
    if (!challenge) throw new RequestError(404, '챌린지를 찾을 수 없어요.')
    return { id, title: challenge.title, timesPerWeek: challenge.this_week.target, canCheck: !challenge.decision_required, checkedToday: challenge.checked_today }
  }
  const response = await apiFetch('/challenges/' + id, { signal })
  await requireSuccess(response, '챌린지를 불러오지 못했어요.')
  const challenge: {
    id: number; title: string; status: string; times_per_week: number;
    participants: { is_me: boolean; status: string }[];
    my_checks: string[];
  } = await response.json()
  return {
    id: challenge.id,
    title: challenge.title,
    timesPerWeek: challenge.times_per_week,
    canCheck: challenge.status === 'ACTIVE' && challenge.participants.some((member) => member.is_me && member.status === 'JOINED'),
    checkedToday: challenge.my_checks.includes(dateInSeoul()),
  }
}

export async function checkChallenge(id: number) {
  if (isChallengeDemo) {
    const challenge = demoChallenges.find((item) => item.id === id)
    if (!challenge) throw new RequestError(404, '챌린지를 찾을 수 없어요.')
    if (!challenge.checked_today) {
      challenge.checked_today = true
      challenge.this_week = { ...challenge.this_week, checked: challenge.this_week.checked + 1 }
    }
    return challenge.this_week
  }
  const response = await apiFetch('/challenges/' + id + '/checks', {
    method: 'POST',
    body: JSON.stringify({ checked_on: dateInSeoul() }),
  })
  await requireSuccess(response, '완료 체크를 저장하지 못했어요.')
  const payload: { this_week: Challenge['this_week'] } = await response.json()
  return payload.this_week
}
