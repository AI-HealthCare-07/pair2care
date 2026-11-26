// frontend/src/api/client.test.ts
// apiFetch 시간 제한: 서버가 멈추면 ApiError(0, TIMEOUT), 화면이 취소한 건 그대로 AbortError

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, TIMEOUT_DETAIL } from './client'

// 응답 없이 멈춘 서버: signal이 끊길 때만 reject
function hangingFetch(_url: string, init: RequestInit): Promise<Response> {
  return new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => reject(init.signal?.reason))
  })
}

// 시간 제한을 손으로 끊을 수 있게 AbortSignal.timeout을 바꿔 끼움
function controllableTimeout() {
  const controller = new AbortController()
  const spy = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(controller.signal)
  return { fire: () => controller.abort(new DOMException('timed out', 'TimeoutError')), spy }
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('apiFetch 시간 제한', () => {
  it('시간이 지나면 ApiError(0, TIMEOUT)', async () => {
    vi.stubGlobal('fetch', vi.fn(hangingFetch))
    const timeout = controllableTimeout()
    const pending = apiFetch('/users/me')
    timeout.fire()
    const error = await pending.catch((problem: unknown) => problem)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, code: 'TIMEOUT', message: TIMEOUT_DETAIL })
    expect(timeout.spy).toHaveBeenCalledWith(10_000)
  })

  it('화면이 취소한 요청은 AbortError 그대로 (시간 초과 아님)', async () => {
    vi.stubGlobal('fetch', vi.fn(hangingFetch))
    controllableTimeout()
    const controller = new AbortController()
    const pending = apiFetch('/users/me', { signal: controller.signal })
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('사진 업로드는 30초', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 201 })))
    const timeout = controllableTimeout()
    await apiFetch('/meals', { method: 'POST', body: new FormData() })
    expect(timeout.spy).toHaveBeenCalledWith(30_000)
  })
})
