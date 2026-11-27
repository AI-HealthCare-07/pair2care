// frontend/src/pages/MyPage.tsx
// S-27 마이 (Figma M18). 건강 정보(검진 수치 입력)·계정(내 정보 + 로그아웃). 설문 고치기·짝꿍/알림 묶음은 화면이 생기면 붙임

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { logout } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import Button from '../components/common/Button'
import '../components/home/home.css'

export default function MyPage() {
  const { state, clear } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const me = state.status === 'authed' ? state.me : null

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout() // 서버가 refresh 쿠키를 지움 (2-4, 로그인 없이도 204)
    } catch {
      // 서버가 안 받아도 이 기기에서는 로그아웃 (메모리 토큰은 logout()이 비움)
    } finally {
      clear() // 가드가 /login으로 보냄 (직접 로그아웃이라 "로그인 뒤 돌아올 주소"는 안 붙음)
    }
  }

  return (
    <section className="home-page" aria-labelledby="my-title">
      <h1 id="my-title" className="home-header__title">
        마이
      </h1>
      <section className="home-card" aria-labelledby="my-health-title">
        <h2 id="my-health-title" className="home-section-title">
          건강 정보
        </h2>
        <p className="home-muted">검진 결과를 넣으면 위험도가 더 정확해져요.</p>
        <Link className="ui-btn ui-btn--secondary" to="/checkup">
          검진 수치 입력하기
        </Link>
      </section>
      <section className="home-card" aria-labelledby="my-account-title">
        <h2 id="my-account-title" className="home-section-title">
          계정
        </h2>
        {me && (
          <p>
            <strong>{me.nickname}</strong>
            <br />
            <span className="home-muted">{me.email}</span>
          </p>
        )}
        <Button variant="secondary" loading={loggingOut} onClick={() => void handleLogout()}>
          {loggingOut ? '로그아웃하고 있어요' : '로그아웃'}
        </Button>
      </section>
    </section>
  )
}
