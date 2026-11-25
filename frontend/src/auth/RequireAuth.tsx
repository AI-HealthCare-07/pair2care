import { Navigate, Outlet, useLocation } from 'react-router-dom'
import Button from '../components/common/Button'
import { useAuth } from './useAuth'
import './auth.css'

const ONBOARDING_PATH = '/onboarding'

export default function RequireAuth() {
  const { state, reload } = useAuth()
  const { pathname } = useLocation()

  if (state.status === 'loading')
    return (
      <p className="auth-status" role="status">
        불러오는 중이에요.
      </p>
    )
  if (state.status === 'error')
    return (
      <div className="auth-status" role="alert">
        <p>내 정보를 불러오지 못했어요.</p>
        <Button variant="secondary" onClick={() => void reload()}>
          다시 시도
        </Button>
      </div>
    )
  if (state.status === 'guest') return <Navigate to="/login" replace /> // 로그인 안 한 사람
  const onOnboarding = pathname === ONBOARDING_PATH
  if (!state.me.has_health_profile && !onOnboarding) return <Navigate to={ONBOARDING_PATH} replace /> // 설문 안 한 사람
  if (state.me.has_health_profile && onOnboarding) return <Navigate to="/home" replace /> // 설문 다시 받으면 409라서 홈으로
  return <Outlet /> // 로그인+설문 했음
}
