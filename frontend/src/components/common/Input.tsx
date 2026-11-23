// frontend/src/components/common/Input.tsx
// 글자 입력창: 위에 라벨, 아래에 안내(hint) 또는 오류(error).
// ⚠️ 임시 모양: 로그인·가입 화면 Figma를 못 봐서 식단 검색창 기준으로 만들었음. 시트 확인 후 수치만 맞추면 됨.

import { useId, type InputHTMLAttributes } from 'react'
import './common.css'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
}

export default function Input({ label, hint, error, id: idProp, className, ...rest }: Props) {
  const autoId = useId()
  const id = idProp ?? autoId
  const noteId = `${id}-note`
  const note = error ?? hint

  return (
    <div className={['ui-field', className].filter(Boolean).join(' ')}>
      <label className="ui-field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className={`ui-field__input${error ? ' has-error' : ''}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        {...rest}
      />
      {note && (
        <p id={noteId} className={`ui-field__note${error ? ' is-error' : ''}`} role={error ? 'alert' : undefined}>
          {note}
        </p>
      )}
    </div>
  )
}
