import { apiFetch, toApiError } from './client'

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

const loadMock = () => import('./challenges.mock')

export async function listChallenges(signal: AbortSignal): Promise<Challenge[]> {
  if (isChallengeDemo) return (await loadMock()).listChallenges()
  const response = await apiFetch('/challenges?status=ACTIVE', { signal })
  if (!response.ok) throw await toApiError(response)
  const payload: { items: Challenge[] } = await response.json()
  return payload.items.filter(({ status, my_status }) => status === 'ACTIVE' && my_status === 'JOINED')
}

export async function readChallenge(id: number, signal: AbortSignal) {
  if (isChallengeDemo) return (await loadMock()).readChallenge(id)
  const response = await apiFetch('/challenges/' + id, { signal })
  if (!response.ok) throw await toApiError(response)
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
  if (isChallengeDemo) return (await loadMock()).checkChallenge(id)
  const response = await apiFetch('/challenges/' + id + '/checks', {
    method: 'POST',
    body: JSON.stringify({ checked_on: dateInSeoul() }),
  })
  if (!response.ok) throw await toApiError(response)
  const payload: { this_week: Challenge['this_week'] } = await response.json()
  return payload.this_week
}

export async function undoChallengeCheck(id: number) {
  if (isChallengeDemo) return (await loadMock()).undoChallengeCheck(id)
  const response = await apiFetch('/challenges/' + id + '/checks/' + dateInSeoul(), { method: 'DELETE' })
  if (!response.ok) throw await toApiError(response)
}

export interface NextChallenge {
  challenge_id: number
  message: string
  source_title: string | null
  source_url: string | null
}

export async function readNextChallenge(signal: AbortSignal): Promise<NextChallenge | null> {
  if (isChallengeDemo) return (await loadMock()).readNextChallenge()
  const response = await apiFetch('/recommendations/challenges/next', { signal, cache: 'no-store' })
  if (!response.ok) throw await toApiError(response)
  return response.json()
}
