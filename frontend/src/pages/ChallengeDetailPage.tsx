import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Button from '../components/common/Button'
import { checkChallenge, readChallenge } from '../api/challenges'
import '../components/recommendation/recommendation.css'

export default function ChallengeDetailPage() {
  const { id } = useParams()
  const [result, setResult] = useState<Awaited<ReturnType<typeof readChallenge>>>()
  const [error, setError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)
  const challengeId = Number(id)

  useEffect(() => {
    if (!Number.isSafeInteger(challengeId) || challengeId < 1) return
    const controller = new AbortController()
    void readChallenge(challengeId, controller.signal).then((challenge) => {
      if (!controller.signal.aborted) setResult(challenge)
    }).catch((problem: unknown) => {
      if (!controller.signal.aborted) setError(problem instanceof Error ? problem.message : '챌린지를 불러오지 못했어요.')
    })
    return () => controller.abort()
  }, [challengeId])

  async function markDone() {
    if (!result?.canCheck || result.checkedToday || saving) return
    setSaving(true)
    setSaveError('')
    try {
      await checkChallenge(challengeId)
      setResult((current) => current?.id === challengeId ? { ...current, checkedToday: true } : current)
    } catch (problem) {
      setSaveError(problem instanceof Error ? problem.message : '완료 체크를 저장하지 못했어요.')
    } finally {
      setSaving(false)
    }
  }

  const validId = Number.isSafeInteger(challengeId) && challengeId > 0
  return (
    <section className="daily-page">
      <Link to="/home">← 홈으로</Link>
      <div className="daily-card">
        <h1>챌린지 상세</h1>
        {!validId || error ? <p role="alert">{error || '챌린지를 찾을 수 없어요.'}</p>
          : result?.id === challengeId ? (
            <>
              <h2>{result.title}</h2>
              <p>기본 목표 주 {result.timesPerWeek}회</p>
              {result.checkedToday ? <p role="status">오늘 완료했어요.</p>
                : result.canCheck && <Button loading={saving} onClick={() => { void markDone() }}>오늘 완료 체크</Button>}
              {saveError && <p role="alert">{saveError}</p>}
            </>
          ) : <p role="status">챌린지를 불러오고 있어요.</p>}
      </div>
    </section>
  )
}
