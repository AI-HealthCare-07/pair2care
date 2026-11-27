// frontend/src/components/home/DailyFeedback.tsx
// "오늘의 한 가지" 아래 도움 돼요 / 별로예요 (11-9, REQ-NFR-019). 별로예요면 이유를 하나 고를 수 있음(선택)
// 이 값은 사용자 만족도라서, 팀이 검토한 뒤에만 가드레일에 반영됨 (X ≠ 부적절)

import { useState } from 'react'
import { ApiError } from '../../api/client'
import { FEEDBACK_REASONS, saveFeedback } from '../../api/recommendationFeedback'
import type { FeedbackReason, MyFeedback } from '../../api/recommendations'
import Chip from '../common/Chip'

interface Props {
  recommendationId: number
  initial: MyFeedback | null
}

export default function DailyFeedback({ recommendationId, initial }: Props) {
  const [feedback, setFeedback] = useState<MyFeedback | null>(initial)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(next: MyFeedback) {
    setSaving(true)
    setError(null)
    try {
      setFeedback(await saveFeedback(recommendationId, next))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '저장하지 못했어요. 다시 눌러 주세요.')
    } finally {
      setSaving(false)
    }
  }

  const pickReason = (reason: FeedbackReason) => void send({ is_helpful: false, reason: feedback?.reason === reason ? null : reason })

  return (
    <div className="home-feedback">
      <div className="home-feedback__row" role="group" aria-label="이 추천이 도움이 됐나요?">
        <Chip selected={feedback?.is_helpful === true} disabled={saving} onClick={() => void send({ is_helpful: true, reason: null })}>
          도움 돼요
        </Chip>
        <Chip
          selected={feedback?.is_helpful === false}
          disabled={saving}
          onClick={() => void send({ is_helpful: false, reason: feedback?.is_helpful === false ? feedback.reason : null })}
        >
          별로예요
        </Chip>
      </div>
      {feedback?.is_helpful === false && (
        <div className="home-feedback__reasons" role="radiogroup" aria-label="별로인 이유 (선택)">
          {FEEDBACK_REASONS.map((item) => (
            <Chip
              key={item.value}
              mode="radio"
              selected={feedback.reason === item.value}
              disabled={saving}
              onClick={() => pickReason(item.value)}
            >
              {item.label}
            </Chip>
          ))}
        </div>
      )}
      <p className="home-muted" role="status">
        {feedback ? '알려 줘서 고마워요. 더 나은 추천을 만드는 데 참고할게요.' : '이 추천이 도움이 됐나요?'}
      </p>
      {error && (
        <p className="ui-field__note is-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
