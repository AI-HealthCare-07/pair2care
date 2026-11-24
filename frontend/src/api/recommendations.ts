import { apiFetch } from './client'

export interface DailyRecommendation {
  target_on: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  content: string | null
  sources: { number: number; title: string; url: string }[] | null
  retry_count: number
}

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

export async function readDaily(signal: AbortSignal, date?: string): Promise<DailyRecommendation | null> {
  const query = date ? '?' + new URLSearchParams({ target_on: date }) : ''
  const response = await apiFetch('/recommendations/daily' + query, { signal })
  if (response.status === 404) return null
  await requireSuccess(response, '오늘의 추천을 불러오지 못했어요.')
  return response.json()
}

export function dateInSeoul(offset = 0): string {
  const seoulDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = (type: string) => Number(seoulDay.find((part) => part.type === type)?.value)
  return new Date(Date.UTC(value('year'), value('month') - 1, value('day') + offset)).toISOString().slice(0, 10)
}
