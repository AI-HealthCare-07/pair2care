import { afterEach, describe, expect, it, vi } from 'vitest'
import { canGiveFeedback, saveFeedback } from './recommendationFeedback'

const source = { number: 1, title: '가이드', url: 'https://example.com' }

describe('canGiveFeedback', () => {
  it('완료됐고 근거가 있을 때만 버튼을 보임', () => {
    expect(canGiveFeedback({ status: 'COMPLETED', sources: [source] })).toBe(true)
    expect(canGiveFeedback({ status: 'COMPLETED', sources: [] })).toBe(false) // 근거 부족
    expect(canGiveFeedback({ status: 'COMPLETED', sources: null })).toBe(false)
    expect(canGiveFeedback({ status: 'PENDING', sources: [source] })).toBe(false)
  })
})

describe('saveFeedback', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('도움 돼요면 reason을 안 보내고, 별로예요면 reason을 보냄', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        const body = JSON.parse(String(init.body))
        bodies.push(body)
        return new Response(JSON.stringify({ recommendation_id: 7, reason: null, ...body, updated_at: 'x' }), { status: 200 })
      }),
    )
    expect(await saveFeedback(7, { is_helpful: true, reason: 'OTHER' })).toEqual({ is_helpful: true, reason: null })
    expect(await saveFeedback(7, { is_helpful: false, reason: 'TOO_HARD' })).toEqual({ is_helpful: false, reason: 'TOO_HARD' })
    expect(bodies).toEqual([{ is_helpful: true }, { is_helpful: false, reason: 'TOO_HARD' }])
  })
})
