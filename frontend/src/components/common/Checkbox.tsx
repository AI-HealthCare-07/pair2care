// frontend/src/components/common/Checkbox.tsx
// 체크박스. Figma M01 약관 동의: 26px 네모, 반경 7px, 체크하면 파랑 채움 + 흰 체크(18px)
// 진짜 <input type="checkbox">를 쓰고 모양만 덮어서 키보드·스크린리더가 그대로 동작함

import type { InputHTMLAttributes, ReactNode } from 'react'
import checkIcon from '../../assets/icon-check.svg'
import './common.css'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  children: ReactNode   // 오른쪽 글자(라벨)
  strong?: boolean      // "전체 동의"처럼 굵게
}

export default function Checkbox({ children, strong = false, className, ...rest }: Props) {
  return (
    <label className={['ui-check', strong && 'ui-check--strong', className].filter(Boolean).join(' ')}>
      <input type="checkbox" className="ui-check__input" {...rest} />
      <span className="ui-check__box" aria-hidden="true">
        <img src={checkIcon} width={18} height={18} alt="" />
      </span>
      <span className="ui-check__label">{children}</span>
    </label>
  )
}
