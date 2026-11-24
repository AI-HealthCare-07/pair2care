import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { checkChallenge, isChallengeDemo, listChallenges, readNextChallenge, undoChallengeCheck } from '../api/challenges'
import { ApiError } from '../api/client'
import type { Challenge, NextChallenge } from '../api/challenges'
import Button from '../components/common/Button'
import ChallengeRow from '../components/common/ChallengeRow'
import '../components/recommendation/recommendation.css'

const remaining = (challenge: Challenge) => challenge.this_week.target - challenge.this_week.checked

export default function HomePage() {
  const navigate = useNavigate()
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [loading, setLoading] = useState(true)
  const [next, setNext] = useState<NextChallenge | null>(null)
  const [recommending, setRecommending] = useState(true)
  const [refresh, setRefresh] = useState(0)
  const [checking, setChecking] = useState<number>()
  const [error, setError] = useState<unknown>(null)
  const checkInFlight = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    void listChallenges(controller.signal).then((items) => {
      if (!controller.signal.aborted) setChallenges(items)
    }).catch((problem: unknown) => {
      if (!controller.signal.aborted) setError(problem)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    void readNextChallenge(controller.signal).then((recommendation) => {
      if (!controller.signal.aborted) setNext(recommendation)
    }).catch(() => {
      if (!controller.signal.aborted) setNext(null)
    }).finally(() => {
      if (!controller.signal.aborted) setRecommending(false)
    })
    return () => controller.abort()
  }, [refresh])

  const eligible = challenges.filter((challenge) => !challenge.checked_today && !challenge.decision_required && remaining(challenge) > 0)
  const recommended = eligible.find((challenge) => challenge.id === next?.challenge_id)
  const completed = challenges.filter(({ checked_today }) => checked_today).length

  async function toggleCheck(challenge: Challenge) {
    if (checkInFlight.current) return
    checkInFlight.current = true
    setChecking(challenge.id)
    setNext(null)
    setError(null)
    try {
      if (challenge.checked_today) await undoChallengeCheck(challenge.id)
      else await checkChallenge(challenge.id)
      reload()
    } catch (problem) {
      setError(problem)
    } finally {
      checkInFlight.current = false
      setChecking(undefined)
    }
  }

  function reload() {
    setError(null)
    setLoading(true)
    setRecommending(true)
    setNext(null)
    setRefresh((value) => value + 1)
  }

  return (
    <section className="daily-page" aria-labelledby="home-title">
      <h1 id="home-title">홈</h1>
      {isChallengeDemo && <p className="daily-context">체험 모드 · 예시 챌린지</p>}
      <div className="daily-card daily-card--next" aria-live="polite">
        <h2>다음 챌린지</h2>
        {loading ? <p role="status">챌린지를 불러오고 있어요.</p> : error ? null : recommending || checking !== undefined ? <p role="status">다음 추천을 확인하고 있어요.</p> : recommended ? (
          <>
            <strong>{next?.message}</strong>
            {next?.source_url && /^https:\/\//.test(next.source_url) && (
              <a className="daily-context" href={next.source_url} target="_blank" rel="noreferrer">{next.source_title}</a>
            )}
            <p className="daily-context">이번 주 목표까지 {remaining(recommended)}회 남았어요.</p>
            <Link className="ui-btn ui-btn--secondary" to={`/challenges/${recommended.id}`}>이 챌린지 보기</Link>
            <p className="daily-context">의료 진단이 아니며 전문가 상담이 필요해요.</p>
          </>
        ) : (
          <p>{challenges.length ? '오늘 추천할 남은 챌린지가 없어요.' : '참여 중인 챌린지가 없어요.'}</p>
        )}
      </div>
      {error != null && (
        <div className="daily-card">
          <p role="alert">{error instanceof ApiError && error.status === 404
            ? '챌린지 서비스를 준비하고 있어요.'
            : error instanceof Error ? error.message : '챌린지 상태를 확인하지 못했어요.'}</p>
          {error instanceof ApiError && error.status === 401
            ? <Link to="/login">로그인하기</Link>
            : <Button variant="secondary" onClick={reload}>다시 확인</Button>}
        </div>
      )}
      {challenges.length > 0 && (
        <section className="daily-challenges" aria-label="오늘 할 챌린지">
          <h2>오늘 할 챌린지 {completed}/{challenges.length}</h2>
          {challenges.map((challenge) => (
            <ChallengeRow
              key={challenge.id}
              title={challenge.title}
              sub={`이번 주 ${challenge.this_week.checked}/${challenge.this_week.target}회`}
              checked={challenge.checked_today}
              meta={checking === challenge.id ? '저장 중' : undefined}
              onToggle={!loading && !error && !challenge.decision_required && checking === undefined
                ? () => { void toggleCheck(challenge) } : undefined}
              onOpen={() => navigate(`/challenges/${challenge.id}`)}
            />
          ))}
        </section>
      )}
    </section>
  )
}
