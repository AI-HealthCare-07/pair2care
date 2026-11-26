import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchMe } from '../api/users'
import { ApiError, onSessionExpired } from '../api/client'
import { AuthContext, type AuthState } from './authContext'

async function loadState(): Promise<AuthState> {
  try {
    return { status: 'authed', me: await fetchMe() }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return { status: 'guest' }
    return { status: 'error' }
  }
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  const reload = useCallback(async () => {
    setState(await loadState())
  }, [])

  const clear = useCallback(() => setState({ status: 'guest', loggedOut: true }), [])

  // 세션 만료(refresh 실패) → guest. loggedOut이 아니라서 가드가 보던 화면을 from에 담아 로그인 뒤 돌려보냄
  useEffect(() => {
    onSessionExpired(() => setState((prev) => (prev.status === 'guest' ? prev : { status: 'guest' })))
    return () => onSessionExpired(null)
  }, [])

  useEffect(() => {
    let ignore = false
    loadState().then((next) => {
      if (!ignore) setState(next)          // 화면이 이미 사라졌으면 무시 (StrictMode에서 두 번 돌아도 안전)
    })
    return () => { ignore = true }
  }, [])

  const value = useMemo(() => ({ state, reload, clear }), [state, reload, clear])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}