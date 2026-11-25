import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function RequireAuth() {
  const { state, reload } = useAuth()
  const { pathname } = useLocation()

  if (state.status === 'loading') return <p className="survey-help">불러오는 중이에요.</p>
  if (state.status === 'error')
    return (
      <div>
        <p>내 정보를 불러오지 못했어요.</p>
        <button type="button" onClick={() => void reload()}>다시 시도</button>
      </div>
    )
  if (state.status === 'guest') return <Navigate to="/login" replace />     // 로그인 안 한 사람
  if (!state.me.has_health_profile && pathname !== '/onboarding') return <Navigate to="/onboarding" replace />  // 로그인은 했는데 설문 안 한 사람
  return <Outlet />     // 로그인+설문 했음
}