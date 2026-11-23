// frontend/src/api/auth.ts
// 인증 API (api.md 2장). 토큰은 client.ts의 메모리에만 저장, refresh 토큰은 서버가 httpOnly 쿠키로 줌

import { apiFetch, setAccessToken, toApiError } from './client'

/** 서버 config.TERMS_VERSION과 같아야 함 (다르면 400 "필수 약관에 모두 동의해 주세요.") */
export const TERMS_VERSION = 'v1.0'

export type Gender = 'MALE' | 'FEMALE'
// 필수 동의 3종: 이용약관 · 개인정보 · 민감정보(건강) (api.md 2-1)
export type Agreement = 'TERMS' | 'PRIVACY' | 'SENSITIVE_HEALTH'

export interface ConsentItem {
  agreement: Agreement
  version: string     // 동의한 약관 버전, TERMS_VERSION을 넣음
  is_agreed: boolean  // 3종 모두 true여야 가입됨
}

export interface SignupBody {
  email: string
  password: string    // 8자 이상, 영문·숫자·특수문자 각 1개 이상 (서버도 다시 검사)
  nickname: string    // 2~20자
  gender: Gender
  birthday: string    // 'YYYY-MM-DD', 만 14세 미만은 400
  consents: ConsentItem[]
}

export interface SignupResult {
  access_token: string
  has_health_profile: boolean   // false면 S-06(가입 설문)으로 보냄
}

/** POST로 JSON을 보내고, 실패하면 ApiError로 던지는 공통 함수 */
async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(
    path,
    { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) },
    // isRetry = true: 401이 와도 토큰 갱신을 시도하지 않음
    // (로그인 실패도 401이라, 비밀번호가 틀릴 때마다 갱신 요청이 헛되이 나가는 것을 막음)
    true,
  )
  // 4xx·5xx면 서버 detail·code·field를 담은 ApiError로 바꿔서 던짐 → 화면에서 catch로 문구 표시
  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return undefined as T // 로그아웃처럼 본문이 없는 응답
  return (await res.json()) as T
}

/** 회원가입 (api.md 2-1): 가입되면 바로 로그인 상태가 되도록 토큰까지 받음 */
export async function signup(body: SignupBody): Promise<SignupResult> {
  const data = await postJson<SignupResult>('/auth/signup', body)
  setAccessToken(data.access_token) // 이후 apiFetch가 Authorization 헤더에 자동으로 붙임
  return data
}

/** 로그인 (api.md 2-2): 틀리면 401, 5번 틀리면 10분 동안 429 (문구는 ApiError.message) */
export async function login(email: string, password: string): Promise<void> {
  const data = await postJson<{ access_token: string }>('/auth/login', { email, password })
  setAccessToken(data.access_token)
}

/** 로그아웃 (api.md 2-4): 로그인 없이 항상 204, 서버가 refresh 쿠키를 지움 */
export async function logout(): Promise<void> {
  await postJson<void>('/auth/logout')
  setAccessToken(null) // 메모리의 access 토큰도 비워서 "로그인 안 한 상태"로 되돌림
}
