// frontend/src/api/events.ts
// 공통 SSE (api.md 12-6) — 화면 전체에서 연결 하나만 열고, 듣는 곳(listener)이 여럿이어도 나눠 줌
//
// 연결 순서
//  1. POST /events/ticket (로그인 필요) → 30초짜리 1회용 티켓
//  2. new EventSource('/api/v1/events?ticket=...') — EventSource는 Authorization 헤더를 못 붙여서 티켓을 씀
//  3. 서버가 보내는 `event: task` → 등록된 listener 모두에게 전달
//
// 끊겼을 때: 브라우저 기본 재연결은 "같은 주소(이미 쓴 티켓)"로 다시 붙어서 401로 끝남
//  → onerror에서 직접 닫고, 잠깐 쉬었다가 새 티켓으로 다시 연결 (3초 → 6초 → … 최대 30초)
// 듣는 곳이 하나도 없으면 연결을 닫음 (홈을 떠나면 끊김)

import { API_BASE, apiFetch } from './client'

/** 12-6 task 이벤트 (결과 내용은 없음 → 받으면 해당 조회 API로 다시 읽음) */
export interface TaskEvent {
  task_id: string
  task_type: 'MEAL_CLASSIFY' | 'RECOMMEND_LLM'
  target_id: number // 식단이면 meals id, 추천이면 recommendations id
  status: 'COMPLETED' | 'FAILED'
}

type Listener = (event: TaskEvent) => void

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const FIRST_RETRY_MS = 3000
const MAX_RETRY_MS = 30_000

const listeners = new Set<Listener>()
let source: EventSource | null = null
let connecting = false // 티켓 받는 중 (그 사이 또 connect가 불려도 두 번 열지 않게)
let retryTimer: ReturnType<typeof setTimeout> | null = null
let retryMs = FIRST_RETRY_MS

async function requestTicket(): Promise<string> {
  const res = await apiFetch('/events/ticket', { method: 'POST' })
  if (!res.ok) throw new Error(`ticket ${res.status}`)
  return ((await res.json()) as { ticket: string }).ticket
}

async function connect(): Promise<void> {
  if (useMock || source || connecting || listeners.size === 0) return
  connecting = true
  try {
    const ticket = await requestTicket()
    if (listeners.size === 0) return // 티켓 받는 사이 화면을 떠났으면 열지 않음
    const opened = new EventSource(`${API_BASE}/events?ticket=${encodeURIComponent(ticket)}`)
    opened.onopen = () => {
      retryMs = FIRST_RETRY_MS // 잘 붙었으면 다음 끊김은 다시 3초부터
    }
    opened.addEventListener('task', (message) => {
      let event: TaskEvent
      try {
        event = JSON.parse((message as MessageEvent<string>).data) as TaskEvent
      } catch {
        return // 모양이 깨진 이벤트 하나 때문에 다른 이벤트를 놓치지 않게 무시
      }
      listeners.forEach((listener) => listener(event))
    })
    opened.onerror = () => {
      opened.close() // 브라우저 기본 재연결(이미 쓴 티켓)을 막고 새 티켓으로 직접 다시 연결
      if (source === opened) source = null
      scheduleReconnect()
    }
    source = opened
  } catch {
    scheduleReconnect() // 티켓을 못 받음(서버 꺼짐·로그아웃 등) → 쉬었다가 다시
  } finally {
    connecting = false
  }
}

function scheduleReconnect() {
  if (retryTimer || listeners.size === 0) return
  retryTimer = setTimeout(() => {
    retryTimer = null
    void connect()
  }, retryMs)
  retryMs = Math.min(retryMs * 2, MAX_RETRY_MS)
}

function disconnect() {
  source?.close()
  source = null
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = null
  retryMs = FIRST_RETRY_MS
}

/** task 이벤트 듣기. 돌려받은 함수를 부르면 그만 들음 (마지막 하나가 그만두면 연결도 닫음) */
export function subscribeTaskEvents(listener: Listener): () => void {
  listeners.add(listener)
  void connect()
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) disconnect()
  }
}

/**
 * 조건에 맞는 task 이벤트가 오거나, timeoutMs가 지나거나, signal이 끊기면 끝나는 Promise.
 * 이벤트를 놓쳐도(연결 전에 끝남·연결 끊김) timeoutMs마다 화면이 직접 다시 확인하게 하는 용도.
 */
export function waitForTask(matches: (event: TaskEvent) => boolean, timeoutMs: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer)
      unsubscribe()
      signal.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, timeoutMs)
    const unsubscribe = subscribeTaskEvents((event) => {
      if (matches(event)) finish()
    })
    signal.addEventListener('abort', finish, { once: true })
  })
}
