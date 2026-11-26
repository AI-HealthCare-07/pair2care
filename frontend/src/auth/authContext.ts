import { createContext } from 'react'
import type { Me } from '../api/users'

export type AuthState =
  | { status: 'loading' }            // 앱 켜지고 /users/me 기다리는 중
  // 401: 로그인 안 됨 (refresh도 실패). loggedOut: 직접 로그아웃함 → 가드가 "로그인 뒤 돌아올 주소"를 안 붙임
  | { status: 'guest'; loggedOut?: true }
  | { status: 'authed'; me: Me }
  | { status: 'error' }              // 서버 고장·네트워크 (로그인 문제 아님 → /login으로 보내면 안 됨)

export interface AuthContextValue {
  state: AuthState
  reload: () => Promise<void>        // 로그인·가입·설문 제출 뒤 다시 불러오기
  clear: () => void                  // 로그아웃 뒤 guest로
}

export const AuthContext = createContext<AuthContextValue | null>(null)