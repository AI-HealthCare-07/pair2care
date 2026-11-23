// frontend/src/components/common/Chip.tsx
// 알약 모양 선택 칩. Figma M21 탭("진행 중 3"), M10 인분 칩(0.5 / 1 / 1.5인분)
//  - mode="pressed" (기본): 켜고 끄는 필터·탭 → aria-pressed
//  - mode="radio": 여럿 중 하나만 고르는 칩 → role="radio" + aria-checked (부모에 role="radiogroup")

import type { ButtonHTMLAttributes } from 'react'
import './common.css'

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'role' | 'aria-pressed' | 'aria-checked'> {
  selected?: boolean
  mode?: 'pressed' | 'radio'
}

export default function Chip({ selected = false, mode = 'pressed', className, type = 'button', children, ...rest }: Props) {
  const a11y = mode === 'radio' ? { role: 'radio' as const, 'aria-checked': selected } : { 'aria-pressed': selected }
  return (
    <button type={type} className={['ui-chip', selected && 'is-selected', className].filter(Boolean).join(' ')} {...a11y} {...rest}>
      {children}
    </button>
  )
}
