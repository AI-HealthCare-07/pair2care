// frontend/src/auth/GuestOnly.tsx
// 시작·가입·로그인 화면 문지기: 이미 로그인한 사람이 오면 보려던 화면(없으면 홈, 설문 전이면 설문)으로 보냄
//  - 로그인 성공 뒤 reload()로 상태가 authed가 되는 순간에도 여기가 먼저 보내므로, 가드가 넘긴 state.from을 같이 봄
//  - 내 정보를 불러오는 중이거나 서버 오류여도 화면은 그대로 보여 줌 (로그인하러 온 사람을 막지 않게)
//  - 가짜 모드에선 화면 확인용으로 건너뜀

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { afterLoginPath, fromState } from './redirect'
import { useAuth } from './useAuth'

// 가짜 모드의 내 정보(MOCK_ME)는 항상 로그인 상태라, 그대로면 시작·가입·로그인 화면을 볼 수 없음 → 가짜 모드에선 건너뜀 (#124와 같은 이유)
const useMock = import.meta.env.VITE_USE_MOCK === 'true'

export default function GuestOnly() {
  const { state } = useAuth()
  const location = useLocation()
  if (state.status === 'authed' && !useMock)
    return <Navigate to={afterLoginPath(fromState(location.state), state.me.has_health_profile)} replace />
  return <Outlet />
}
