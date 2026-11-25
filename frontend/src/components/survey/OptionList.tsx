// frontend/src/components/survey/OptionList.tsx
// 보기 목록 (가로 꽉 찬 알약, 선택하면 연한 파랑). 하나만 고르는 radiogroup.
// 키보드: Tab은 선택된 보기(없으면 첫 보기)로, 방향키(↑↓←→)·Home·End로 옮기면 바로 선택됨 (WAI-ARIA 라디오 그룹)

import type { KeyboardEvent } from 'react'
import Chip from '../common/Chip'
import { moveRadioFocus } from '../common/radioKeys'
import type { AnswerValue, QuestionOption } from '../../survey/types'
import './survey.css'

interface Props {
  /** 질문 제목 요소의 id (그룹 이름으로 읽힘) */
  labelledBy: string
  options: QuestionOption[]
  value: AnswerValue | null | undefined
  onChange: (value: AnswerValue) => void
}

export default function OptionList({ labelledBy, options, value, onChange }: Props) {
  const selectedIndex = options.findIndex((o) => o.value === value)
  const tabbableIndex = selectedIndex >= 0 ? selectedIndex : 0

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const next = moveRadioFocus(e)
    if (next !== null) onChange(options[next].value)
  }

  return (
    <div className="survey-options" role="radiogroup" aria-labelledby={labelledBy} onKeyDown={handleKeyDown}>
      {options.map((option, i) => (
        <Chip
          key={String(option.value)}
          mode="radio"
          className="survey-option"
          selected={option.value === value}
          tabIndex={i === tabbableIndex ? 0 : -1}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Chip>
      ))}
    </div>
  )
}
