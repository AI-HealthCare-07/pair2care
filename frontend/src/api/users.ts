// frontend/src/api/users.ts
// 내 정보 (api.md 2-5). 인증 가드(AuthContext)가 앱 켜질 때 한 번 부름
// 토큰이 없거나 만료면 apiFetch가 refresh 쿠키로 재발급 → 다시 요청까지 알아서 함 → 그래도 안 되면 401

import { apiFetch, toApiError } from './client'
import type { Gender } from './auth'

export interface Me {
  id: number
  email: string
  nickname: string
  gender: Gender
  birthday: string               // 'YYYY-MM-DD'
  region: string | null
  has_health_profile: boolean    // false면 가드가 /onboarding으로 보냄 (1단계에서 추가한 값)
  created_at: string
}

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

// 가짜 모드(백엔드 없이 화면 볼 때)에서도 가드가 /login으로 막지 않게 고정값
const MOCK_ME: Me = {
  id: 1, email: 'demo@example.com', nickname: '데모', gender: 'MALE',
  birthday: '1980-01-01', region: null, has_health_profile: true, created_at: '2026-11-25T00:00:00+09:00',
}

export async function fetchMe(): Promise<Me> {
  if (useMock) return MOCK_ME
  const res = await apiFetch('/users/me')
  if (!res.ok) throw await toApiError(res) // 401이면 apiFetch가 refresh까지 시도한 뒤라 진짜 로그아웃 상태
  return (await res.json()) as Me
}