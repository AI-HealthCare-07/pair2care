// frontend/src/components/home/ConditionPicker.tsx
// 홈 "오늘 컨디션" (REQ-DASH-005, S-12). 좋음·보통·나쁨 중 하나, 누르면 바로 저장 (같은 날은 서버가 덮어씀)
// 저장이 실패하면 고르기 전 값으로 되돌리고 안내

import { useEffect, useRef, useState } from 'react'
import { getTodayCondition, saveCondition, type ConditionValue } from '../../api/healthLogs'
import Chip from '../common/Chip'

const OPTIONS: { value: ConditionValue; label: string }[] = [
  { value: 2, label: '😊 좋음' },
  { value: 1, label: '🙂 보통' },
  { value: 0, label: '😣 나쁨' },
]

export default function ConditionPicker() {
  const [selected, setSelected] = useState<ConditionValue | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const saved = useRef<ConditionValue | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getTodayCondition(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        saved.current = value
        setSelected(value)
      })
      .catch(() => {
        // 못 읽어도 고르기는 가능 (저장하면 오늘 값이 생김)
      })
    return () => controller.abort()
  }, [])

  async function choose(value: ConditionValue) {
    if (saving || value === saved.current) return
    setSelected(value)
    setSaving(true)
    setMessage(null)
    try {
      await saveCondition(value)
      saved.current = value
      setMessage('오늘 컨디션을 기록했어요.')
    } catch {
      setSelected(saved.current)
      setMessage('저장하지 못했어요. 다시 눌러 주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="home-card" aria-labelledby="home-condition-title">
      <h2 id="home-condition-title" className="home-section-title">
        오늘 컨디션은 어때요?
      </h2>
      <div className="home-condition" role="radiogroup" aria-labelledby="home-condition-title" aria-busy={saving || undefined}>
        {OPTIONS.map((option) => (
          <Chip
            key={option.value}
            mode="radio"
            selected={selected === option.value}
            disabled={saving}
            onClick={() => void choose(option.value)}
          >
            {option.label}
          </Chip>
        ))}
      </div>
      {message && (
        <p className="home-muted" role="status">
          {message}
        </p>
      )}
    </section>
  )
}
