// frontend/src/components/record/RecordChart.tsx
// 최근 2주 꺾은선 (Figma M07 혈압 카드). 혈압은 수축기·이완기 2줄, 나머지는 1줄
// 라이브러리 없이 SVG polyline 하나: 값 개수가 적고(2주) 상호작용이 없어서 충분함

import { chartLines } from '../../records/recordView'

const WIDTH = 300
const HEIGHT = 120

interface Props {
  series: { label: string; values: number[] }[]
  summary: string // 스크린리더용 한 줄 ("최근 2주 혈압 기록 5개, 마지막 132/84 mmHg")
}

export default function RecordChart({ series, summary }: Props) {
  const lines = chartLines(
    series.map((line) => line.values),
    WIDTH,
    HEIGHT,
  )
  return (
    <figure className="record-chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={summary} preserveAspectRatio="none">
        {lines.map((points, i) => (
          <polyline key={series[i].label} points={points} className={`record-chart__line record-chart__line--${i}`} />
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
