// frontend/src/pages/LoginPage.tsx
// S-04 로그인 (Figma M14). 실패하면 비밀번호 아래 주의 문구, 성공하면 설문 여부에 따라 S-06 또는 홈

import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/common/Button'
import Input from '../components/common/Input'
import { login } from '../api/auth'
import { ApiError } from '../api/client'
import { afterLoginPath, fromState } from '../auth/redirect'
import { useAuth } from '../auth/useAuth'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { reload } = useAuth()
  const [forgotOpen, setForgotOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [alert, setAlert] = useState<string[] | null>(null) // 오류 문구 줄들
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!email.trim() || !password) {
      setAlert(['이메일과 비밀번호를 입력해 주세요.'])
      return
    }
    setLoading(true)
    setAlert(null)
    try {
      const result = await login(email.trim(), password)
      await reload()
      navigate(afterLoginPath(fromState(location.state), result.has_health_profile), { replace: true }) // 보려던 화면이 있으면 거기로
    } catch (err) {
      setAlert(toAlert(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="로그인"
      greeting={['다시 만나서 반가워요 👋', '오늘 습관도 이어가 볼까요?']}
      onSubmit={handleSubmit}
      actions={
        <>
          <Button type="submit" fullWidth loading={loading}>
            {loading ? '로그인하고 있어요' : '로그인'}
          </Button>
          <div className="auth__links auth__links--spread">
            {/* 비밀번호 찾기(S-05, P2) 화면이 생기기 전까지는 404 대신 준비 중 안내 */}
            <button type="button" className="auth__link-button" aria-expanded={forgotOpen} onClick={() => setForgotOpen(true)}>
              비밀번호를 잊으셨나요?
            </button>
            <span aria-hidden="true">·</span>
            <Link to="/signup">회원가입</Link>
          </div>
          {forgotOpen && (
            <p className="auth__note" role="status">
              비밀번호 찾기는 준비 중이에요. 운영진에게 문의해 주세요.
            </p>
          )}
        </>
      }
    >
      <Input
        label="이메일"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        placeholder="example@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Input
        label="비밀번호"
        type="password"
        name="password"
        autoComplete="current-password"
        placeholder="비밀번호 입력"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {alert && (
        <p className="auth__alert" role="alert">
          ⚠️ {alert[0]}
          {alert[1] && (
            <>
              <br />
              {alert[1]}
            </>
          )}
        </p>
      )}
    </AuthLayout>
  )
}

/** 서버 오류를 화면 문구로. 401은 잠금 규칙을 같이 알려 줌 (S-04) */
function toAlert(err: unknown): string[] {
  if (err instanceof ApiError) {
    if (err.status === 401) return [err.message, '(5회 틀리면 10분 잠금)']
    if (err.status === 429) return [err.message] // "로그인을 5번 틀려서 10분 뒤에 다시 시도할 수 있어요."
    if (err.status === 422) return ['이메일 형식과 비밀번호(8자 이상)를 확인해 주세요.']
  }
  return ['로그인하지 못했어요. 잠시 후 다시 시도해 주세요.']
}
