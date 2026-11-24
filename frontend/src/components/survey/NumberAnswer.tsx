// frontend/src/components/survey/NumberAnswer.tsx
// 숫자 문항(키·몸무게·허리둘레·하루 개비). 입력칸 + 단위. 화면에는 질문 제목이 있어서 라벨은 스크린리더용으로만 둠.
// 입력 중에는 글자(text)를 따로 들고 있다가(예: "172."), 숫자로 바꿔서 위로 올림. 비우면 undefined(안 답함).

import { useState, type ChangeEvent } from 'react'
import Input from '../common/Input'
import type { AnswerValue, Question } from '../../survey/types'
import './survey.css'

interface Props {
  question: Question
  /** 스크린리더가 읽을 이름 (질문 문구) */
  labelText: string
  value: AnswerValue | null | undefined
  onChange: (value: number | undefined) => void
  error?: string
}

export default function NumberAnswer({ question, labelText, value, onChange, error }: Props) {
  const [text, setText] = useState(typeof value === 'number' && Number.isFinite(value) ? String(value) : '')

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    // 숫자와 점 하나만 허용
    const cleaned = e.target.value.replace(/[^0-9.]/g, '').replace(/(\..*)\./g, '$1')
    setText(cleaned)
    onChange(cleaned === '' ? undefined : Number(cleaned))
  }

  return (
    <div className="survey-number">
      <Input
        className="survey-number__input"
        label={labelText}
        hideLabel
        inputMode="decimal"
        autoComplete="off"
        value={text}
        onChange={handleChange}
        error={error}
      />
      {question.unit && <span className="survey-number__unit">{question.unit}</span>}
    </div>
  )
}
