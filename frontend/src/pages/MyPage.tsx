// frontend/src/pages/MyPage.tsx
// S-27 마이 (Figma M18). 건강 정보(검진 수치 입력)·데이터 활용(선택 동의 켜기·끄기, 2-6)·계정(내 정보 + 로그아웃). 설문 고치기·짝꿍/알림 묶음은 화면이 생기면 붙임

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { logout } from '../api/auth'
import { ApiError } from '../api/client'
import { getConsents, saveConsent } from '../api/consents'
import { useAuth } from '../auth/useAuth'
import Button from '../components/common/Button'
import Checkbox from '../components/common/Checkbox'
import '../components/home/home.css'

export default function MyPage() {
  const { state, clear } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const me = state.status === 'authed' ? state.me : null
  const [modelImprovement, setModelImprovement] = useState<boolean | null>(null) // null = 불러오는 중·실패
  const [consentSaving, setConsentSaving] = useState(false)
  const [consentError, setConsentError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getConsents()
      .then((items) => {
        if (alive) setModelImprovement(items.find((i) => i.agreement === 'MODEL_IMPROVEMENT')?.is_agreed ?? false)
      })
      .catch(() => {
        if (alive) setConsentError('동의 상태를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.')
      })
    return () => {
      alive = false
    }
  }, [])

  async function toggleModelImprovement() {
    if (modelImprovement === null) return
    const next = !modelImprovement
    setConsentSaving(true)
    setConsentError(null)
    try {
      const saved = await saveConsent('MODEL_IMPROVEMENT', next)
      setModelImprovement(saved.is_agreed)
    } catch (err) {
      setConsentError(err instanceof ApiError ? err.message : '저장하지 못했어요. 다시 시도해 주세요.')
    } finally {
      setConsentSaving(false)
    }
  }

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
      <section className="home-card" aria-labelledby="my-data-title">
        <h2 id="my-data-title" className="home-section-title">
          데이터 활용
        </h2>
        <Checkbox
          checked={modelImprovement === true}
          disabled={modelImprovement === null || consentSaving}
          onChange={() => void toggleModelImprovement()}
        >
          (선택) 예측 모델 개선에 내 데이터 활용
        </Checkbox>
        <p className="home-muted">
          동의한 뒤의 설문·검진만 이름 없이 학습에 써요. 끄면 다음 학습부터 빠져요.
        </p>
        {consentError && (
          <p className="ui-field__note is-error" role="alert">
            {consentError}
          </p>
        )}
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
