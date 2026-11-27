// frontend/src/pages/RecordsPage.tsx
// S-19 기록 탭 (Figma M07) · REQ-DASH-001·002 · api.md 6-2
//  - 주소 /records/<kind> (kind: blood-pressure · blood-glucose · weight · steps · exercise · alcohol), /records만 오면 혈압으로
//  - 식단 탭은 현지 님 MealsPage(/records/meals)로 이동 (RecordTabs가 같은 탭 줄을 그림)
//  - 카드: 최근 2주 그래프(7-2 하루 평균, 가로는 날짜) + 최근 기록 목록(6-2 원래 값) + [+ 오늘 ○○ 기록하기] → 입력 화면(M07-c)
//  - 혈압 탭엔 고혈압, 혈당 탭엔 당뇨 위험도 추이 카드 (7-1, RiskTrendCard)
// 다음 PR: 이번 주 챌린지 달성률 카드 (8장 챌린지 API 머지 뒤)

import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getDailyPoints, type DayPoint } from '../api/dashboard'
import { listHealthLogs, type HealthLog } from '../api/healthLogs'
import MedicalNotice from '../components/common/MedicalNotice'
import RecordChart from '../components/record/RecordChart'
import RecordTabs from '../components/record/RecordTabs'
import RiskTrendCard from '../components/record/RiskTrendCard'
import '../components/record/record.css'
import { DEFAULT_RECORD_KIND, formatLogValue, recordTypeOf, type RecordType } from '../records/recordTypes'
import { dayPosition, logTimeLabel, recentRange } from '../records/recordView'

const LIST_LIMIT = 7 // 목록엔 최근 7개만 (그래프는 2주 전부)

type Load = { logs: HealthLog[]; days: DayPoint[]; from: string } | { error: string }

export default function RecordsPage() {
  const { kind } = useParams()
  const type = recordTypeOf(kind)
  if (!type) return <Navigate to={`/records/${DEFAULT_RECORD_KIND}`} replace />
  return (
    <main className="record-page">
      <h1 className="record-page__title">기록</h1>
      <RecordTabs />
      {/* key: 탭을 바꾸면 카드 상태(불러오는 중·오류)를 새로 시작 */}
      <RecordCard key={type.kind} type={type} />
      {type.trendDisease && <RiskTrendCard key={`trend-${type.kind}`} disease={type.trendDisease} />}
      <MedicalNotice />
    </main>
  )
}

function RecordCard({ type }: { type: RecordType }) {
  const [load, setLoad] = useState<Load | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const { from, to } = recentRange()
    // 목록은 원래 기록(6-2), 그래프는 하루 평균(7-2) → 둘 다 같은 2주
    Promise.all([listHealthLogs(type.logType, from, to, controller.signal), getDailyPoints(type.logType, from, to, controller.signal)])
      .then(([logs, days]) => setLoad({ logs, days, from }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoad({ error: error instanceof ApiError ? error.message : '기록을 불러오지 못했어요.' })
      })
    return () => controller.abort()
  }, [type, retryKey])

  const titleId = `record-${type.kind}-title`
  return (
    <section className="record-card" aria-labelledby={titleId}>
      <div className="record-card__head">
        <h2 id={titleId} className="record-card__title">
          {type.title}
          {type.logType === 'BLOOD_PRESSURE' && ' · 집에서 잰 값'}
        </h2>
        <span className="record-muted">최근 2주</span>
      </div>

      {load === null && <p role="status">기록을 불러오고 있어요.</p>}
      {load && 'error' in load && (
        <div role="alert">
          <p>{load.error}</p>
          <button type="button" className="record-link" onClick={() => setRetryKey((k) => k + 1)}>
            다시 불러오기
          </button>
        </div>
      )}
      {load && 'logs' in load && <RecordHistory type={type} logs={load.logs} days={load.days} from={load.from} />}

      <Link className="ui-btn ui-btn--secondary ui-btn--full" to={`/records/${type.kind}/new`}>
        + 오늘 {type.title} 기록하기
      </Link>
    </section>
  )
}

function RecordHistory({ type, logs, days, from }: { type: RecordType; logs: HealthLog[]; days: DayPoint[]; from: string }) {
  if (logs.length === 0) return <p className="record-muted">최근 2주 동안 기록이 없어요. 오늘 처음 기록해 볼까요?</p>

  const last = logs[logs.length - 1]
  const at = (day: DayPoint) => dayPosition(day.date, from)
  const series =
    type.logType === 'BLOOD_PRESSURE'
      ? [
          { label: '수축기', points: days.map((day) => ({ x: at(day), y: day.value })) },
          { label: '이완기', points: days.map((day) => ({ x: at(day), y: day.value2 ?? day.value })) },
        ]
      : [{ label: type.title, points: days.map((day) => ({ x: at(day), y: day.value })) }]
  const recent = logs.slice(-LIST_LIMIT).reverse() // 최신이 위로

  return (
    <>
      <RecordChart
        series={series}
        summary={`최근 2주 ${type.title} 기록 ${logs.length}개, 마지막 ${formatLogValue(type, last.value, last.value2)}`}
      />
      <ul className="record-list" aria-label={`최근 ${type.title} 기록`}>
        {recent.map((log) => (
          <li key={log.id} className="record-list__row">
            <span className="record-muted">{logTimeLabel(log.measured_at)}</span>
            <strong>{formatLogValue(type, log.value, log.value2)}</strong>
          </li>
        ))}
      </ul>
    </>
  )
}
