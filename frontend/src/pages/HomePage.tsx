import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../components/common/Button'
import { apiFetch } from '../api/client'
import { dateInSeoul, readDaily, requireSuccess, RequestError } from '../api/recommendations'
import type { DailyRecommendation } from '../api/recommendations'
import '../components/recommendation/recommendation.css'

const isDemo = import.meta.env.VITE_USE_MOCK === 'true'

export default function HomePage() {
  const [recommendation, setRecommendation] = useState<DailyRecommendation | null>(null)
  const [queryDate, setQueryDate] = useState<string>()
  const [reading, setReading] = useState(!isDemo)
  const [refresh, setRefresh] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<Error>()
  const request = useRef<AbortController | null>(null)
  const isPending = recommendation?.status === 'PENDING' || recommendation?.status === 'PROCESSING'

  useEffect(() => () => request.current?.abort(), [])

  useEffect(() => {
    if (isDemo) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const result = await readDaily(controller.signal, queryDate)
        if (controller.signal.aborted) return
        setRecommendation(result)
        if (result?.status === 'PENDING' || result?.status === 'PROCESSING') {
          timer = setTimeout(load, 2500)
        }
      } catch (problem) {
        if (!controller.signal.aborted) setError(problem instanceof Error ? problem : new Error('조회에 실패했어요.'))
      } finally {
        if (!controller.signal.aborted) setReading(false)
      }
    }
    void load()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [queryDate, refresh])

  async function generate() {
    if (request.current) return
    const controller = new AbortController()
    request.current = controller
    setSubmitting(true)
    setError(undefined)
    try {
      const today = dateInSeoul()
      const response = await apiFetch('/recommendations/daily', { method: 'POST', signal: controller.signal })
      await requireSuccess(response, '추천을 시작하지 못했어요.')
      setQueryDate(today)
      setRefresh((value) => value + 1)
      setReading(true)
    } catch (problem) {
      if (!controller.signal.aborted) setError(problem instanceof Error ? problem : new Error('요청에 실패했어요.'))
    } finally {
      request.current = null
      if (!controller.signal.aborted) setSubmitting(false)
    }
  }

  const completed = recommendation?.status === 'COMPLETED'
  const hasEvidence = completed && Boolean(recommendation.sources?.length)
  const failed = recommendation?.status === 'FAILED'
  const limitReached = failed && recommendation.retry_count >= 3

  return (
    <section className="daily-page" aria-labelledby="daily-title">
      <h1 id="daily-title">오늘의 한 가지</h1>
      <div className="daily-card">
        {isDemo ? (
          <>
            <p className="daily-context">체험 모드 · 예시 기록</p>
            <h2>오늘 점심 후, 짝꿍과 10분 걸어볼까요?</h2>
            <p>최근 7일 동안 점심 후 걷기 2회</p>
            <Link className="ui-btn ui-btn--accent ui-btn--full" to="/challenges/new">짝꿍과 챌린지 만들기</Link>
          </>
        ) : (
          <>
            {reading || (isPending && !error) ? <p role="status">{isPending ? '추천을 준비하고 있어요.' : '추천을 불러오고 있어요.'}</p> : null}
            {error && <p role="alert">{error.message}</p>}
            {error instanceof RequestError && error.status === 401 ? <Link to="/login">로그인하기</Link> : error && (
              <Button variant="secondary" onClick={() => { setError(undefined); setReading(true); setRefresh((value) => value + 1) }}>다시 확인</Button>
            )}
            {!reading && !error && !recommendation && <Button fullWidth loading={submitting} onClick={generate}>오늘의 추천 받기</Button>}
            {!reading && !error && failed && (
              <>
                <p>{limitReached ? '오늘의 추천을 다시 요청할 수 있는 횟수를 모두 사용했어요.' : '추천을 만들지 못했어요.'}</p>
                {!limitReached && <Button fullWidth loading={submitting} onClick={generate}>다시 요청하기</Button>}
              </>
            )}
            {completed && (
              <>
                <h2>{recommendation.content}</h2>
                {recommendation.sources?.length ? (
                  <ul className="daily-sources">
                    {recommendation.sources.filter(({ url }) => /^https:\/\//i.test(url)).map((source) => (
                      <li key={source.number}><a href={source.url} target="_blank" rel="noreferrer">[{source.number}] {source.title}</a></li>
                    ))}
                  </ul>
                ) : null}
                {hasEvidence && <Link className="ui-btn ui-btn--accent ui-btn--full" to="/challenges/new">짝꿍과 챌린지 만들기</Link>}
              </>
            )}
          </>
        )}
      </div>
    </section>
  )
}
