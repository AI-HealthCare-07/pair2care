// frontend/src/pages/RecordFormPage.tsx
// 기록 입력 (Figma M07-c 혈압 기록, 다른 항목도 같은 틀) · api.md 6-1
//  - 칸이 비었거나 숫자가 아니면 보내기 전에 막음. 범위·소수점은 서버가 검사하고 400 문구를 그대로 보여 줌
//  - 날짜·시간 기본값은 지금(서울), 미래는 못 고르게 max (서버도 5분 여유 두고 막음)
//  - 저장하면 그 항목 탭으로 돌아감
// 빠진 것: Figma의 아침·저녁 칩은 저장할 칸이 없어서(6-1에 필드 없음) 이번엔 시각으로만 구분

import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { createHealthLog } from '../api/healthLogs'
import Button from '../components/common/Button'
import Input from '../components/common/Input'
import TopBar from '../components/common/TopBar'
import '../components/record/record.css'
import { parseFieldValue, recordTypeOf, type RecordField, type RecordType } from '../records/recordTypes'
import { nowInSeoulInput } from '../records/recordView'

export default function RecordFormPage() {
  const { kind } = useParams()
  const type = recordTypeOf(kind)
  if (!type) return <Navigate to="/records" replace />
  return <RecordForm type={type} />
}

function RecordForm({ type }: { type: RecordType }) {
  const navigate = useNavigate()
  const [now] = useState(nowInSeoulInput)
  const [texts, setTexts] = useState<Record<RecordField['key'], string>>({ value: '', value2: '' })
  const [measuredAt, setMeasuredAt] = useState(now)
  const [missing, setMissing] = useState<RecordField['key'] | null>(null) // 비어 있는 첫 칸
  const [serverError, setServerError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const back = () => navigate(`/records/${type.kind}`, { replace: true })

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (saving) return
    const values = type.fields.map((field) => [field.key, parseFieldValue(texts[field.key])] as const)
    const empty = values.find(([, value]) => value === null)
    if (empty) {
      setMissing(empty[0])
      document.getElementById(`record-${empty[0]}`)?.focus()
      return
    }
    setMissing(null)
    setServerError(null)
    setSaving(true)
    try {
      const [[, value], second] = values as [readonly ['value', number], (readonly ['value2', number])?]
      await createHealthLog({ log_type: type.logType, value, ...(second ? { value2: second[1] } : {}), measured_at: measuredAt })
      back()
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : '저장하지 못했어요. 잠시 후 다시 시도해 주세요.')
      setSaving(false)
    }
  }

  return (
    <div className="record-form-screen">
      <TopBar title={`오늘 ${type.title} 기록`} onBack={back} />
      <form className="record-form" onSubmit={(event) => void submit(event)} noValidate>
        <h2 className="record-form__title">{type.title} 기록하기</h2>
        {type.hint && <p className="record-muted">{type.hint}</p>}

        <div className={type.fields.length > 1 ? 'record-form__pair' : undefined}>
          {type.fields.map((field) => (
            <Input
              key={field.key}
              id={`record-${field.key}`}
              label={field.label}
              placeholder={field.placeholder}
              inputMode={field.decimal ? 'decimal' : 'numeric'}
              value={texts[field.key]}
              onChange={(event) => setTexts((prev) => ({ ...prev, [field.key]: event.target.value }))}
              error={missing === field.key ? '숫자를 입력해 주세요.' : undefined}
            />
          ))}
        </div>

        <Input
          label="날짜·시간"
          type="datetime-local"
          value={measuredAt}
          max={now}
          onChange={(event) => setMeasuredAt(event.target.value)}
        />

        {serverError && (
          <p className="record-form__error" role="alert">
            {serverError}
          </p>
        )}
        <Button type="submit" fullWidth loading={saving}>
          저장하기
        </Button>
        <Button type="button" variant="ghost" fullWidth onClick={back}>
          취소
        </Button>
      </form>
    </div>
  )
}
