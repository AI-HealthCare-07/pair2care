// frontend/src/components/record/RecordChart.tsx
// 최근 2주 꺾은선 (Figma M07 혈압 카드). 혈압은 수축기·이완기 2줄, 나머지는 1줄. 점은 하루 평균(7-2 bucket=day), 가로 위치는 날짜
// 라이브러리 없이 SVG polyline 하나: 값 개수가 적고(2주) 상호작용이 없어서 충분함

import { chartLines, type ChartPoint } from '../../records/recordView'

const WIDTH = 300
const HEIGHT = 120

interface Props {
  series: { label: string; points: ChartPoint[] }[]
  summary: string // 스크린리더용 한 줄 ("최근 2주 혈압 기록 5개, 마지막 132/84 mmHg")
}

export default function RecordChart({ series, summary }: Props) {
  const lines = chartLines(
    series.map((line) => line.points),
    WIDTH,
    HEIGHT,
  )
  return (
    <figure className="record-chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={summary} preserveAspectRatio="none">
        {lines.map((points, i) => (
          <g key={series[i].label} className={`record-chart__series record-chart__series--${i}`}>
            <polyline points={points} className="record-chart__line" />
            {/* 점: 기록이 하루뿐이면 선이 안 보여서 점으로 표시.
                preserveAspectRatio="none"이라 circle은 타원으로 늘어나서, 길이 0인 선의 둥근 끝(non-scaling-stroke)으로 그림 */}
            {points.split(' ').filter(Boolean).map((xy) => {
              const [x, y] = xy.split(',')
              return <line key={xy} x1={x} y1={y} x2={x} y2={y} className="record-chart__dot-mark" />
            })}
          </g>
        ))}
      </svg>
      {series.length > 1 && (
        <figcaption className="record-chart__legend">
          {series.map((line, i) => (
            <span key={line.label}>
              <i className={`record-chart__dot record-chart__dot--${i}`} aria-hidden="true" />
              {line.label}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  )
}
