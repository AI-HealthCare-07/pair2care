// frontend/src/components/common/Select.tsx
// 목록에서 고르는 칸. Figma 컴포넌트 "Select": 높이 56px, 반경 12px, 왼쪽 16px·오른쪽 12px, 오른쪽에 chevron(20px)
// 아직 안 고르면(Empty) 회색 "년"·"월"·"일", 고르면 진한 글자. 누르면 휴대폰 기본 휠·목록이 뜸(네이티브 <select>)

import type { SelectHTMLAttributes } from 'react'
import chevronIcon from '../../assets/icon-chevron-down.svg'
import './common.css'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  /** 화면에 라벨 글자가 따로 없어서 스크린리더용 이름이 꼭 필요함 ("태어난 해") */
  'aria-label': string
  placeholder: string                          // 안 골랐을 때 보이는 글자 ("년")
  options: { value: string; label: string }[]
}

export default function Select({ placeholder, options, value, className, ...rest }: Props) {
  return (
    <div className={['ui-select', className].filter(Boolean).join(' ')}>
      <select className={`ui-select__control${value ? '' : ' is-empty'}`} value={value} {...rest}>
        <option value="" disabled>
          {placeholder}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <img className="ui-select__icon" src={chevronIcon} width={20} height={20} alt="" aria-hidden="true" />
    </div>
  )
}
