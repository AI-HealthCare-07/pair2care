// frontend/src/components/record/RiskTrendCard.tsx
// 기록 탭 아래 "고혈압(당뇨) 위험도 추이" 카드 (Figma M07) · api.md 7-1, 5-3
//  - 최근 4주, 주마다 마지막 예측 1개를 막대로 (예측 없는 주는 막대 없음)
//  - 마지막 점이 직전보다 낮을 때만 "낮아졌어요" + 달라진 응답 (5-3 changed_inputs, REQ-NFR-003)
//  - 진단받은 질환(managed)이거나 예측이 하나도 없으면 카드를 숨김 (관리 중 안내는 S-09·홈 몫)

import { useEffect, useState } from 'react'
import { getRiskTrend, type TrendPoint } from '../../api/dashboard'
import { predictionsApi } from '../../api/predictionsApi'
import type { Disease } from '../../api/predictions'
import { DISEASE_LABEL, LEVEL_LABEL } from '../../prediction/labels'
import { barPercent, changedInputText, droppedPrediction, TREND_WEEKS, weekLabel } from '../../records/riskTrend'

interface Trend {
  points: TrendPoint[]
  dropNote: string | null // 낮아졌을 때만 "달라진 응답: …"
}

export default function RiskTrendCard({ disease }: { disease: Disease }) {
  const [trend, setTrend] = useState<Trend | null>(null)

  useEffect(() => {
    let ignore = false
    async function load() {
      const series = (await getRiskTrend(TREND_WEEKS)).find((s) => s.disease === disease)
      if (!series || series.managed || series.points.length === 0) return null
      const droppedId = droppedPrediction(series.points)
      let dropNote: string | null = null
      if (droppedId !== null) {
        const detail = await predictionsApi.getPrediction(droppedId)
        const changes = detail.method === 'MODEL' ? changedInputText(detail.changed_inputs ?? []) : ''
        dropNote = changes ? `달라진 응답: ${changes}` : null
      }
      return { points: series.points, dropNote }
    }
    load()
      .then((next) => {
        if (!ignore) setTrend(next)
      })
      .catch(() => {
        // 추이는 보조 카드라 못 불러오면 조용히 숨김 (위 기록 카드는 그대로)
      })
    return () => {
      ignore = true
    }
  }, [disease])

  if (!trend) return null
  const titleId = `trend-${disease}-title`
  const last = trend.points[trend.points.length - 1]

  return (
    <section className="record-card" aria-labelledby={titleId}>
      <div className="record-card__head">
        <h2 id={titleId} className="record-card__title">
          {DISEASE_LABEL[disease]} 위험도 추이
        </h2>
        <span className="record-muted">최근 {TREND_WEEKS}주</span>
      </div>
      <ol className="trend-bars" aria-label={`주별 ${DISEASE_LABEL[disease]} 위험도, 마지막 ${LEVEL_LABEL[last.level]}`}>
        {trend.points.map((point) => (
          <li key={point.week_start} className="trend-bars__item">
            <span className="trend-bars__track" aria-hidden="true">
              <span className={`trend-bars__bar trend-bars__bar--${point.level}`} style={{ height: `${barPercent(point.score)}%` }} />
            </span>
            <span className="trend-bars__label">
              {weekLabel(point.week_start)}
              <span className="ui-visually-hidden"> {LEVEL_LABEL[point.level]}</span>
            </span>
          </li>
        ))}
      </ol>
      {trend.dropNote && (
        <p className="trend-note">
          지난번보다 위험도가 낮아졌어요.
          <br />
          {trend.dropNote}
        </p>
      )}
    </section>
  )
}
