// frontend/src/components/home/DailyActionCard.tsx
// 홈 "오늘의 한 가지" (11-1·11-2, Figma M05 맨 위 카드)
//  1. 11-2 조회 → 오늘 저장본이 없으면(404) 11-1로 생성 요청
//  2. PENDING·PROCESSING이면 3초마다 11-2를 다시 확인 (완료 알림 SSE 12-6이 생기면 바꿈), 1분 넘으면 멈추고 "다시 확인"
//  3. FAILED면 다시 만들기 (retry_count 3이면 서버가 429라 버튼 대신 안내)
// 의료 안내(C-01)는 카드 상태와 상관없이 보이도록 HomePage 맨 아래에 한 번 둠 (#119 리뷰)

import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  getDailyRecommendation,
  isRetryLimit,
  requestDailyRecommendation,
  type DailyRecommendation,
} from '../../api/recommendations'
import { canGiveFeedback } from '../../api/recommendationFeedback'
import { usedSources } from '../../home/homeView'
import Button from '../common/Button'
import DailyFeedback from './DailyFeedback'

const POLL_MS = 3000
const MAX_POLLS = 20 // 3초 × 20 = 1분
const MAX_RETRY = 3 // api.md 11-5: 최초 1번 + 재생성 2번

type View =
  | { kind: 'loading' }
  | { kind: 'waiting'; slow: boolean } // 워커가 만드는 중
  | { kind: 'done'; recommendation: DailyRecommendation }
  | { kind: 'failed'; canRetry: boolean }
  | { kind: 'error'; message: string }

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => clearTimeout(timer), { once: true })
  })

function toView(rec: DailyRecommendation): View {
  if (rec.status === 'COMPLETED') return { kind: 'done', recommendation: rec }
  if (rec.status === 'FAILED') return { kind: 'failed', canRetry: rec.retry_count < MAX_RETRY }
  return { kind: 'waiting', slow: false }
}

/** 저장본을 읽고, 없거나 다시 만들어야 하면 생성 요청 → 끝날 때까지 기다림 */
async function loadDaily(signal: AbortSignal, onView: (view: View) => void, forceCreate: boolean): Promise<void> {
  let rec = forceCreate ? null : await getDailyRecommendation(signal)
  if (!rec) {
    await requestDailyRecommendation()
    rec = await getDailyRecommendation(signal)
  }
  for (let poll = 0; rec && (rec.status === 'PENDING' || rec.status === 'PROCESSING'); poll += 1) {
    if (poll >= MAX_POLLS) {
      onView({ kind: 'waiting', slow: true })
      return
    }
    onView({ kind: 'waiting', slow: false })
    await sleep(POLL_MS, signal)
    if (signal.aborted) return
    rec = await getDailyRecommendation(signal)
  }
  onView(rec ? toView(rec) : { kind: 'error', message: '오늘의 한 가지를 불러오지 못했어요.' })
}

export default function DailyActionCard() {
  const [view, setView] = useState<View>({ kind: 'loading' })
  const [run, setRun] = useState({ key: 0, forceCreate: false })

  useEffect(() => {
    const controller = new AbortController()
    const onView = (next: View) => {
      if (!controller.signal.aborted) setView(next)
    }
    loadDaily(controller.signal, onView, run.forceCreate).catch((error: unknown) => {
      if (controller.signal.aborted) return
      if (isRetryLimit(error)) onView({ kind: 'failed', canRetry: false })
      else onView({ kind: 'error', message: error instanceof ApiError ? error.message : '오늘의 한 가지를 불러오지 못했어요.' })
    })
    return () => controller.abort()
  }, [run])

  const recheck = () => {
    setView({ kind: 'loading' })
    setRun((prev) => ({ key: prev.key + 1, forceCreate: false }))
  }
  const recreate = () => {
    setView({ kind: 'loading' })
    setRun((prev) => ({ key: prev.key + 1, forceCreate: true }))
  }

  return (
    <section className="home-card home-card--daily" aria-labelledby="home-daily-title" aria-live="polite">
      <h2 id="home-daily-title" className="home-card__eyebrow">
        💡 오늘의 한 가지
      </h2>
      {view.kind === 'loading' && <p role="status">오늘의 한 가지를 불러오고 있어요.</p>}
      {view.kind === 'waiting' && (
        <>
          <p role="status">{view.slow ? '조금 오래 걸리고 있어요.' : '오늘에 맞는 한 가지를 고르고 있어요.'}</p>
          {view.slow && (
            <Button variant="secondary" onClick={recheck}>
              다시 확인
            </Button>
          )}
        </>
      )}
      {view.kind === 'done' && <DailyContent recommendation={view.recommendation} />}
      {view.kind === 'failed' && (
        <>
          <p>오늘의 한 가지를 만들지 못했어요.</p>
          {view.canRetry ? (
            <Button variant="secondary" onClick={recreate}>
              다시 만들기
            </Button>
          ) : (
            <p className="home-muted">오늘은 다시 만들 수 있는 횟수를 모두 썼어요. 내일 다시 찾아올게요.</p>
          )}
        </>
      )}
      {view.kind === 'error' && (
        <>
          <p role="alert">{view.message}</p>
          <Button variant="secondary" onClick={recheck}>
            다시 확인
          </Button>
        </>
      )}
    </section>
  )
}

function DailyContent({ recommendation }: { recommendation: DailyRecommendation }) {
  const content = recommendation.content ?? ''
  const sources = usedSources(content, recommendation.sources ?? [])
  return (
    <>
      <p className="home-daily__content">{content}</p>
      {sources.length > 0 && (
        <ul className="home-daily__sources" aria-label="근거">
          {sources.map((source) => (
            <li key={source.number}>
              근거:{' '}
              {/^https:\/\//.test(source.url) ? (
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>
              ) : (
                source.title
              )}{' '}
              [{source.number}]
            </li>
          ))}
        </ul>
      )}
      {canGiveFeedback(recommendation) && (
        <DailyFeedback recommendationId={recommendation.id} initial={recommendation.my_feedback ?? null} />
      )}
    </>
  )
}
