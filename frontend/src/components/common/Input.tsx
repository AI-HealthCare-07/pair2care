// frontend/src/components/common/Input.tsx
// 글자 입력창: 위에 라벨, 아래에 안내(hint) 또는 오류(error). Figma 컴포넌트 시트 "Input" 기준.
// hideLabel: 질문 제목이 이미 화면에 있어서 라벨을 또 보여 줄 필요가 없을 때 (스크린리더는 라벨을 읽음)

import { useId, type CSSProperties, type InputHTMLAttributes } from 'react'
import './common.css'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
  hideLabel?: boolean
}

const visuallyHidden: CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
}

export default function Input({ label, hint, error, hideLabel = false, id: idProp, className, ...rest }: Props) {
  const autoId = useId()
  const id = idProp ?? autoId
  const noteId = `${id}-note`
  const note = error ?? hint

  return (
    <div className={['ui-field', className].filter(Boolean).join(' ')}>
      <label className="ui-field__label" htmlFor={id} style={hideLabel ? visuallyHidden : undefined}>
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
