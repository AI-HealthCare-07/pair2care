// frontend/src/components/common/TopBar.tsx
// 상단 바. Figma 컴포넌트 시트 "TopBar": 375×56px 고정, 좌우 패딩 12px, 간격 8px, 배경 color/surface(#FFFFFF)
// 하단 탭이 없는 화면(M10·M11·M21)에서 ‹ 제목. 오른쪽에 버튼 등을 넣을 수 있음.

import type { ReactNode } from 'react'
import './common.css'

interface Props {
  title: string
  /** 없으면 뒤로 가기 버튼을 그리지 않음 */
  onBack?: () => void
  right?: ReactNode
}

export default function TopBar({ title, onBack, right }: Props) {
  return (
    <header className="ui-topbar">
      {onBack && (
        <button type="button" className="ui-topbar__back" onClick={onBack} aria-label="뒤로 가기">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
      )}
      <h1 className="ui-topbar__title">{title}</h1>
      {right && <div className="ui-topbar__right">{right}</div>}
    </header>
  )
}
