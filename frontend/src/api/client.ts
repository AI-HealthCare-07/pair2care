const API_BASE = '/api/v1'

// access 토큰은 메모리에만 둠 (localStorage는 XSS에 털릴 수 있어서 X)
let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
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
  const res = await fetch(`${API_BASE}/auth/token/refresh`, {
    method: 'GET',              // 지금 백엔드 기준. api.md 2-3대로 POST로 바뀌면 같이 바꿈
    credentials: 'include',     // 쿠키(refresh_token)를 같이 보내라는 값
  })
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

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })

  // 토큰이 만료됐으면 한 번만 새로 받아서 다시 시도
  if (res.status === 401 && !isRetry) {     // "인증 안 됨" 상태 코드
    const ok = await refreshAccessToken()
    if (ok) return apiFetch(path, options, true)
    setAccessToken(null)
  }
  return res
}