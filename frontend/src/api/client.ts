export const API_BASE = '/api/v1'

// 서버가 응답 없이 멈춰도 로딩만 계속 보이지 않게 끊는 시간. 사진 업로드는 느린 망을 생각해 길게
const TIMEOUT_MS = 10_000
const UPLOAD_TIMEOUT_MS = 30_000
export const TIMEOUT_DETAIL = '서버 응답이 늦어요. 잠시 후 다시 시도해 주세요.'

// AbortSignal.any는 Safari 17.4부터라, 없으면 컨트롤러 하나에 두 신호를 이어 붙임 (#130 현지 님 리뷰)
export function anySignal(signals: AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === 'function') return AbortSignal.any(signals)
  const controller = new AbortController()
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason)
      break
    }
    signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true })
  }
  return controller.signal
}

// 화면이 넘긴 signal(페이지 이동 취소)과 시간 제한 중 먼저 오는 쪽으로 끊음. 시간 초과만 ApiError(0, TIMEOUT)로 바꿈
async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const timeout = AbortSignal.timeout(timeoutMs)
  const signal = init.signal ? anySignal([init.signal, timeout]) : timeout
  try {
    return await fetch(url, { ...init, signal })
  } catch (problem) {
    if (timeout.aborted && !init.signal?.aborted) throw new ApiError(0, TIMEOUT_DETAIL, 'TIMEOUT')
    throw problem
  }
}

// access 토큰은 메모리에만 둠 (localStorage는 XSS에 털릴 수 있어서 X)
let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

// 쓰다가 refresh까지 실패(세션 만료)하면 AuthProvider가 guest로 바뀌도록 알림.
// 안 알리면 인증 상태가 authed로 남아서, 화면이 /login으로 보내도 GuestOnly가 /home으로 되돌려 보냄
let sessionExpiredListener: (() => void) | null = null

export function onSessionExpired(listener: (() => void) | null) {
  sessionExpiredListener = listener
}

// 동시에 401이 여러 개 와도 refresh는 한 번만 나가도록, 진행 중인 요청을 같이 기다림
let refreshing: Promise<boolean> | null = null

function refreshAccessToken(): Promise<boolean> {
  if (!refreshing) {
    refreshing = requestRefresh().finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

async function requestRefresh(): Promise<boolean> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/token/refresh`,
    {
      method: 'POST',           // 상태를 바꾸는 요청 (api.md 2-3)
      credentials: 'include',   // 쿠키(refresh_token)를 같이 보내라는 값
    },
    TIMEOUT_MS,
  )
  if (!res.ok) return false
  const data = await res.json()
  setAccessToken(data.access_token)      // 응답에서 새 access 토큰이 들어 있는 키 이름
  return true
}

export async function apiFetch(path: string, options: RequestInit = {}, isRetry = false): Promise<Response> {
  const headers = new Headers(options.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)   // 토큰 앞에 붙는 인증 방식 이름
  // FormData(사진 업로드)는 브라우저가 boundary까지 넣어 주므로 Content-Type을 직접 넣지 않음
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const timeoutMs = options.body instanceof FormData ? UPLOAD_TIMEOUT_MS : TIMEOUT_MS
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' }, timeoutMs)

  // 토큰이 만료됐으면 한 번만 새로 받아서 다시 시도
  if (res.status === 401 && !isRetry) {     // "인증 안 됨" 상태 코드
    const ok = await refreshAccessToken()
    if (ok) return apiFetch(path, options, true)
    setAccessToken(null)
    sessionExpiredListener?.()
  }
  return res
}

// 서버 에러를 화면에서 쓰기 좋게 바꾼 것. code·field는 서버가 줄 때만 값이 있음 (api.md 1장)
export class ApiError extends Error {
  status: number
  code: string | null
  field: string | null      // 3-1 설문 400에서 어느 문항인지 (현지님 S-06이 씀)
  constructor(status: number, detail: string, code: string | null = null, field: string | null = null) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  let detail = '요청을 처리하지 못했어요.'
  let code: string | null = null
  let field: string | null = null
  try {
    const body = await res.json()
    // 422는 detail이 배열이라 문자열일 때만 씀 (meals.ts와 같은 규칙)
    if (typeof body.detail === 'string') detail = body.detail
    if (typeof body.code === 'string') code = body.code
    if (typeof body.field === 'string') field = body.field
  } catch {
    // 본문이 JSON이 아니면 기본 문구
  }
  return new ApiError(res.status, detail, code, field)
}
