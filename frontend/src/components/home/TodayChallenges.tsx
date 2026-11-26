// frontend/src/components/home/TodayChallenges.tsx
// 홈 "오늘 할 챌린지" + 맨 위 "다음 챌린지"(11-8). 체크·추천 흐름은 민준 님 임시 홈(#92) 그대로 옮김
// 8장 챌린지 API가 머지되기 전 진짜 서버에서는 404 → "챌린지 서비스를 준비하고 있어요"

import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  checkChallenge,
  isChallengeDemo,
  listChallenges,
  readNextChallenge,
  undoChallengeCheck,
  type Challenge,
  type NextChallenge,
} from '../../api/challenges'
import { ApiError } from '../../api/client'
import Button from '../common/Button'
import ChallengeRow from '../common/ChallengeRow'

const remaining = (challenge: Challenge) => challenge.this_week.target - challenge.this_week.checked

export default function TodayChallenges() {
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
    void listChallenges(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setChallenges(items)
      })
      .catch((problem: unknown) => {
        if (!controller.signal.aborted) setError(problem)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    void readNextChallenge(controller.signal)
      .then((recommendation) => {
        if (!controller.signal.aborted) setNext(recommendation)
      })
      .catch(() => {
        if (!controller.signal.aborted) setNext(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setRecommending(false)
      })
    return () => controller.abort()
  }, [refresh])

  const eligible = challenges.filter(
    (challenge) => !challenge.checked_today && !challenge.decision_required && remaining(challenge) > 0,
  )
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
    <section className="home-challenges" aria-labelledby="home-challenges-title">
      <div className="home-challenges__head">
        <h2 id="home-challenges-title" className="home-section-title">
          오늘 할 챌린지{challenges.length > 0 && ` ${completed}/${challenges.length}`}
        </h2>
        <Link className="home-link" to="/challenges">
          전체 보기
        </Link>
      </div>
      {isChallengeDemo && <p className="home-muted">체험 모드 · 예시 챌린지</p>}

      {!loading && !error && !recommending && checking === undefined && recommended && next && (
        <div className="home-card" aria-live="polite">
          <h3 className="home-card__eyebrow">다음 챌린지</h3>
          <strong>{next.message}</strong>
          {next.source_url && /^https:\/\//.test(next.source_url) && (
            <a className="home-muted" href={next.source_url} target="_blank" rel="noreferrer">
              {next.source_title}
            </a>
          )}
          <p className="home-muted">이번 주 목표까지 {remaining(recommended)}회 남았어요.</p>
          <Link className="ui-btn ui-btn--secondary" to={`/challenges/${recommended.id}`}>
            이 챌린지 보기
          </Link>
        </div>
      )}

      {loading && <p role="status">챌린지를 불러오고 있어요.</p>}
      {error != null && (
        <div className="home-card">
          <p role="alert">
            {error instanceof ApiError && error.status === 404
              ? '챌린지 서비스를 준비하고 있어요.'
              : error instanceof Error
                ? error.message
                : '챌린지 상태를 확인하지 못했어요.'}
          </p>
          <Button variant="secondary" onClick={reload}>
            다시 확인
          </Button>
        </div>
      )}
      {!loading && !error && challenges.length === 0 && <p className="home-muted">참여 중인 챌린지가 없어요.</p>}
      {challenges.map((challenge) => (
        <ChallengeRow
          key={challenge.id}
          title={challenge.title}
          sub={`이번 주 ${challenge.this_week.checked}/${challenge.this_week.target}회`}
          checked={challenge.checked_today}
          meta={checking === challenge.id ? '저장 중' : undefined}
          onToggle={
            !loading && !error && !challenge.decision_required && checking === undefined
              ? () => {
                  void toggleCheck(challenge)
                }
              : undefined
          }
          onOpen={() => navigate(`/challenges/${challenge.id}`)}
        />
      ))}
    </section>
  )
}
