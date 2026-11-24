// frontend/src/components/auth/AuthLayout.tsx
// 가입(M01)·로그인(M14) 공통 틀: 상단 바 → 로고·서비스명 → 큰 인사말 → 입력 영역 → 아래 버튼 영역
// Figma: 본문 패딩 24px·간격 20px, 아래 영역 위 12px·좌우 24px·아래 34px·간격 8px

import type { FormEvent, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../common/TopBar'
import logo from '../../assets/logo.png'
import './auth.css'

interface Props {
  title: string            // 상단 바 제목
  greeting: [string, string] // 큰 인사말 두 줄
  onSubmit: (e: FormEvent<HTMLFormElement>) => void
  children: ReactNode      // 입력칸들
  actions: ReactNode       // 아래 버튼·링크
}

export default function AuthLayout({ title, greeting, onSubmit, children, actions }: Props) {
  const navigate = useNavigate()
  return (
    <div className="auth">
      <TopBar title={title} onBack={() => navigate('/')} />
      <form className="auth__form" onSubmit={onSubmit} noValidate>
        <div className="auth__content">
          <div className="auth__brand">
            {/* 512px 원본에서 심볼만 보이게 Figma와 같은 비율로 잘라 보여 줌 */}
            <span className="auth__logo" aria-hidden="true">
              <img src={logo} alt="" />
            </span>
            <span className="auth__name">
              Pair <span className="auth__name-2">2</span> Care
            </span>
          </div>
          <h2 className="auth__greeting">
            {greeting[0]}
            <br />
            {greeting[1]}
          </h2>
          {children}
        </div>
        <div className="auth__actions">{actions}</div>
      </form>
    </div>
  )
}
