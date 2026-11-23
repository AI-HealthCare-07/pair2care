// frontend/src/components/common/Button.tsx
// 공통 버튼. Figma 컴포넌트 시트 "Button": 높이 56px(접근성 기준), 반경 14px, 좌우 패딩 24px
// 화면 폭에 꽉 채울 때(시트의 327px)는 fullWidth
//  - primary   : 다음·저장 (파랑 채움)
//  - secondary : 보조 (흰 바탕 + 파랑 테두리)
//  - accent    : 짝꿍 관련 (#5B5BE8, 토큰 color/accent)
//  - ghost     : 건너뛰기 (바탕 없는 글자 버튼)
// loading은 누를 수 없게 하고 aria-busy만 붙임. 문구("저장하고 있어요")는 호출하는 쪽에서 바꿈.

import type { ButtonHTMLAttributes } from 'react'
import './common.css'

export type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'ghost'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  fullWidth?: boolean
  loading?: boolean
}

export default function Button({
  variant = 'primary',
  fullWidth = false,
  loading = false,
  disabled,
  className,
  type = 'button',
  children,
  ...rest
}: Props) {
  const classes = ['ui-btn', `ui-btn--${variant}`, fullWidth && 'ui-btn--full', className].filter(Boolean).join(' ')
  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {children}
    </button>
  )
}
