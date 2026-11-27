// frontend/src/pages/CheckupPage.tsx
// S-07 검진 수치 입력 (Figma M03, wireframe.md S-07) · api.md 4-1
//  - 날짜 + 혈압·공복혈당·허리둘레, 중성지방·HDL·당화혈색소는 "더 입력하기"로 접어 둠. 모두 선택이지만 최소 1개
//  - 보내기 전에 checkCheckup으로 범위까지 막고(서버 422는 칸별 문구가 없어서), 400은 서버 문구를 그대로 보여 줌
//  - 저장하면 서버가 예측을 다시 계산 → S-09로. prediction_error면 검진은 저장됐다고 알리고 머묾
//  - ?focus=fasting_glucose 처럼 오면 그 칸으로 바로 이동 (S-09 "검진 수치를 더 입력하면" 링크용, 접힌 칸이면 펼침)
// 빠진 것: 결과지 사진으로 채우기(S-08 OCR, 12/4 이후 김지연), 지난 검진 고치기(4-2·4-4, 마이)

import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { dateInSeoul } from '../api/challenges'
import { createCheckup } from '../api/checkups'
import { ApiError } from '../api/client'
import Button from '../components/common/Button'
import Input from '../components/common/Input'
import TopBar from '../components/common/TopBar'
import '../components/record/record.css'
import { CHECKUP_FIELDS, checkCheckup, isCheckupKey, type CheckupField, type CheckupKey } from '../checkup/checkupFields'

const SAVE_FAILED = '저장하지 못했어요. 잠시 후 다시 시도해 주세요.'
const PREDICTION_FAILED = '검진은 저장했어요. 위험도 계산만 잠깐 안 됐어요. 검진을 다시 저장하면 다시 계산돼요.'
const PHOTO_SOON = '결과지 사진으로 채우기는 준비 중이에요. 지금은 직접 입력해 주세요.'

export default function CheckupPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const focusKey = params.get('focus')
  const [today] = useState(() => dateInSeoul())
  const [checkedOn, setCheckedOn] = useState(today)
  const [texts, setTexts] = useState<Partial<Record<CheckupKey, string>>>({})
  const [showMore, setShowMore] = useState(() => CHECKUP_FIELDS.some((field) => field.more && field.key === focusKey))
  const [fieldError, setFieldError] = useState<{ key: CheckupKey | 'checked_on'; message: string } | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [photoNote, setPhotoNote] = useState(false)
  const [saving, setSaving] = useState(false)

  // 앱 안에서 들어왔으면 뒤로, 주소로 바로 열었으면 홈으로
  const back = () => (location.key === 'default' ? navigate('/home', { replace: true }) : navigate(-1))

  useEffect(() => {
    if (isCheckupKey(focusKey)) document.getElementById(`checkup-${focusKey}`)?.focus()
  }, [focusKey])

  function focusField(key: CheckupKey | 'checked_on') {
    if (CHECKUP_FIELDS.some((field) => field.more && field.key === key)) setShowMore(true)
    // 펼친 뒤 그려진 칸에 포커스
    requestAnimationFrame(() => document.getElementById(`checkup-${key}`)?.focus())
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (saving) return
    setFieldError(null)
    setFormError(null)
    const check = checkCheckup(checkedOn, texts, today)
    if (!check.ok) {
      if (check.field) {
        setFieldError({ key: check.field, message: check.message })
        focusField(check.field)
      } else {
        setFormError(check.message)
      }
      return
    }
    setSaving(true)
    try {
      const saved = await createCheckup(check.checkedOn, check.values)
      if (saved.predictionError) {
        setFormError(PREDICTION_FAILED)
        setSaving(false)
        return
      }
      navigate('/prediction', { replace: true })
    } catch (error) {
      setFormError(error instanceof ApiError && error.status === 400 ? error.message : SAVE_FAILED)
      setSaving(false)
    }
  }

  const renderField = (field: CheckupField) => (
    <Input
      key={field.key}
      id={`checkup-${field.key}`}
      label={`${field.label} (${field.unit})`}
      placeholder={field.placeholder}
      inputMode={field.decimal ? 'decimal' : 'numeric'}
      value={texts[field.key] ?? ''}
      onChange={(event) => setTexts((prev) => ({ ...prev, [field.key]: event.target.value }))}
      error={fieldError?.key === field.key ? fieldError.message : undefined}
    />
  )
  const [systolic, diastolic, ...basic] = CHECKUP_FIELDS.filter((field) => !field.more)

  return (
    <div className="record-form-screen">
      <TopBar title="검진 수치 (선택)" onBack={back} />
      <form className="record-form" onSubmit={(event) => void submit(event)} noValidate>
        <h2 className="record-form__title">
          검진 결과가 있으면
          <br />
          더 정확해져요
        </h2>
        <p className="record-muted">없어도 괜찮아요. 설문만으로도 위험도를 볼 수 있어요.</p>

        <Button type="button" variant="secondary" fullWidth onClick={() => setPhotoNote(true)}>
          결과지 사진으로 채우기
        </Button>
        {photoNote && (
          <p className="record-muted" role="status">
            {PHOTO_SOON}
          </p>
        )}

        <Input
          id="checkup-checked_on"
          label="검진 받은 날짜"
          type="date"
          value={checkedOn}
          max={today}
          onChange={(event) => setCheckedOn(event.target.value)}
          error={fieldError?.key === 'checked_on' ? fieldError.message : undefined}
        />

        <div className="record-form__pair">
          {renderField(systolic)}
          {renderField(diastolic)}
        </div>
        {basic.map(renderField)}

        <details className="checkup-more" open={showMore} onToggle={(event) => setShowMore(event.currentTarget.open)}>
          <summary>더 입력하기 (중성지방 · HDL · 당화혈색소)</summary>
          <div className="checkup-more__fields">{CHECKUP_FIELDS.filter((field) => field.more).map(renderField)}</div>
        </details>

        {formError && (
          <p className="record-form__error" role="alert">
            {formError}
          </p>
        )}
        <Button type="submit" fullWidth loading={saving}>
          {saving ? '저장하고 있어요' : '위험도 보기'}
        </Button>
        <Button type="button" variant="ghost" fullWidth onClick={back}>
          건너뛰기
        </Button>
      </form>
    </div>
  )
}
