// frontend/src/api/events.test.ts
// 공통 SSE 클라이언트: 티켓으로 연결, task 이벤트 나눠 주기, 끊기면 새 티켓으로 다시, 듣는 곳이 없으면 닫기

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { subscribeTaskEvents, waitForTask, type TaskEvent } from './events'

// 브라우저 EventSource 대신 쓰는 가짜: 만들어진 것들을 모아 두고 테스트가 이벤트를 직접 쏨
class FakeEventSource {
  static all: FakeEventSource[] = []
  url: string
  closed = false
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private handlers: Record<string, ((message: { data: string }) => void)[]> = {}
  constructor(url: string) {
    this.url = url
    FakeEventSource.all.push(this)
  }
  addEventListener(name: string, handler: (message: { data: string }) => void) {
    ;(this.handlers[name] ??= []).push(handler)
  }
  close() {
    this.closed = true
  }
  emit(name: string, data: unknown) {
    this.handlers[name]?.forEach((handler) => handler({ data: JSON.stringify(data) }))
  }
}

const TASK: TaskEvent = { task_id: 't1', task_type: 'RECOMMEND_LLM', target_id: 42, status: 'COMPLETED' }
let ticketNo = 0
const flush = () => vi.advanceTimersByTimeAsync(0) // 티켓 fetch(Promise)가 끝나게 한 바퀴 돌림

beforeEach(() => {
  vi.useFakeTimers()
  FakeEventSource.all = []
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ ticket: `ticket-${++ticketNo}`, expires_in: 30 }), { status: 200 })),
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('subscribeTaskEvents', () => {
  it('티켓으로 연결 하나만 열고, task 이벤트를 듣는 곳 모두에게 줌', async () => {
    const a = vi.fn()
    const b = vi.fn()
    const stopA = subscribeTaskEvents(a)
    const stopB = subscribeTaskEvents(b)
    await flush()
    expect(FakeEventSource.all).toHaveLength(1)
    expect(FakeEventSource.all[0].url).toMatch(/^\/api\/v1\/events\?ticket=ticket-\d+$/)
    FakeEventSource.all[0].emit('task', TASK)
    expect(a).toHaveBeenCalledWith(TASK)
    expect(b).toHaveBeenCalledWith(TASK)
    stopA()
    stopB()
  })

  it('끊기면 닫고 3초 뒤 새 티켓으로 다시 연결', async () => {
    const stop = subscribeTaskEvents(() => {})
    await flush()
    const first = FakeEventSource.all[0]
    first.onerror?.()
    expect(first.closed).toBe(true)
    await vi.advanceTimersByTimeAsync(3000)
    expect(FakeEventSource.all).toHaveLength(2)
    expect(FakeEventSource.all[1].url).not.toBe(first.url) // 다른 티켓
    stop()
  })

  it('마지막으로 듣던 곳이 그만두면 연결을 닫음', async () => {
    const stop = subscribeTaskEvents(() => {})
    await flush()
    stop()
    expect(FakeEventSource.all[0].closed).toBe(true)
  })
})

describe('waitForTask', () => {
  it('맞는 이벤트가 오면 바로 끝나고, 다른 이벤트는 무시', async () => {
    const keep = subscribeTaskEvents(() => {})
    await flush()
    const done = vi.fn()
    void waitForTask((e) => e.target_id === 42, 10_000, new AbortController().signal).then(done)
    FakeEventSource.all[0].emit('task', { ...TASK, target_id: 7 })
    await flush()
    expect(done).not.toHaveBeenCalled()
    FakeEventSource.all[0].emit('task', TASK)
    await flush()
    expect(done).toHaveBeenCalled()
    expect(FakeEventSource.all[0].closed).toBe(false) // 기다림이 끝나도 카드가 연 연결은 유지
    keep()
  })

  it('알림이 안 오면 시간이 지나서 끝남 (화면이 직접 다시 확인)', async () => {
    const done = vi.fn()
    void waitForTask(() => true, 10_000, new AbortController().signal).then(done)
    await vi.advanceTimersByTimeAsync(10_000)
    expect(done).toHaveBeenCalled()
  })
})
