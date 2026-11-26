// frontend/src/pages/RecordsPage.tsx
// S-19 기록 탭 (Figma M07) · REQ-DASH-001·002 · api.md 6-2
//  - 주소 /records/<kind> (kind: blood-pressure · blood-glucose · weight · steps · exercise · alcohol), /records만 오면 혈압으로
//  - 식단 탭은 현지 님 MealsPage(/records/meals)로 이동 (RecordTabs가 같은 탭 줄을 그림)
//  - 카드: 최근 2주 그래프 + 최근 기록 목록 + [+ 오늘 ○○ 기록하기] → 입력 화면(/records/<kind>/new, Figma M07-c)
// 다음 PR: 위험도 추이(7-2)·이번 주 챌린지 달성률(8-13) 카드 (Figma M07 아래 두 카드)

import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { listHealthLogs, type HealthLog } from '../api/healthLogs'
import MedicalNotice from '../components/common/MedicalNotice'
import RecordChart from '../components/record/RecordChart'
import RecordTabs from '../components/record/RecordTabs'
import '../components/record/record.css'
import { DEFAULT_RECORD_KIND, formatLogValue, recordTypeOf, type RecordType } from '../records/recordTypes'
import { logTimeLabel, recentRange } from '../records/recordView'

const LIST_LIMIT = 7 // 목록엔 최근 7개만 (그래프는 2주 전부)

type Load = { kind: string; logs: HealthLog[] } | { kind: string; error: string }

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
    listHealthLogs(type.logType, from, to, controller.signal)
      .then((logs) => setLoad({ kind: type.kind, logs }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoad({ kind: type.kind, error: error instanceof ApiError ? error.message : '기록을 불러오지 못했어요.' })
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
      {load && 'logs' in load && <RecordHistory type={type} logs={load.logs} />}

      <Link className="ui-btn ui-btn--secondary ui-btn--full" to={`/records/${type.kind}/new`}>
        + 오늘 {type.title} 기록하기
      </Link>
    </section>
  )
}

function RecordHistory({ type, logs }: { type: RecordType; logs: HealthLog[] }) {
  if (logs.length === 0) return <p className="record-muted">최근 2주 동안 기록이 없어요. 오늘 처음 기록해 볼까요?</p>

  const last = logs[logs.length - 1]
  const series =
    type.logType === 'BLOOD_PRESSURE'
      ? [
          { label: '수축기', values: logs.map((log) => log.value) },
          { label: '이완기', values: logs.map((log) => log.value2 ?? log.value) },
        ]
      : [{ label: type.title, values: logs.map((log) => log.value) }]
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
