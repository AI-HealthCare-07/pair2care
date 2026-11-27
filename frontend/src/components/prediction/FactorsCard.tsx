// frontend/src/components/prediction/FactorsCard.tsx
// 영향을 준 요인 (Figma M04 아래 카드). factors는 질환마다 따로 계산돼서 질환 소제목으로 나눔 (성은 님 11/25).
// 요인이 하나도 없는 질환은 소제목째 숨기고, 모든 질환이 비면 카드 자체를 안 그림.
// 줄 오른쪽 "+5~9살 / −1~4살 / +20살 이상": 같은 성별 평균보다 건강 나이를 몇 살 정도 올리거나 내리는지
//   (5-3 factors[].years 정수를 화면에서 구간으로, #114 · 11/27 범위 표시). null이면 숨김
// 숫자가 하나라도 보이면 맨 아래 ℹ️에 그 뜻을 한 줄 더함 (#123 성은 님)
// 맨 아래 ℹ️: 요인 후보에서 나이를 뺀 이유 (#107, 팀장님 11/25 위치 확정)

import { AGE_IN_SCORE_NOTICE, DISEASE_LABEL, YEARS_NOTICE } from '../../prediction/labels'
import type { FactorLine } from '../../prediction/view'
import type { Disease } from '../../api/predictions'
import './prediction.css'

export interface FactorGroup {
  disease: Disease
  lines: FactorLine[]
}

const ARROW = { UP: '▲', DOWN: '▼' } as const
const ARROW_LABEL = { UP: '위험을 높이는 요인', DOWN: '위험을 낮추는 요인' } as const

export default function FactorsCard({ groups }: { groups: FactorGroup[] }) {
  const shown = groups.filter((g) => g.lines.length > 0)
  if (shown.length === 0) return null
  const hasYears = shown.some((g) => g.lines.some((line) => line.years !== null))

  return (
    <section className="pred-card" aria-labelledby="pred-factors-title">
      <h3 className="pred-card__name" id="pred-factors-title">영향을 준 요인</h3>

      {shown.map((group) => (
        <div className="pred-factors__group" key={group.disease}>
          <h4 className="pred-factors__disease">{DISEASE_LABEL[group.disease]}</h4>
          <ul className="pred-factors__list">
            {group.lines.map((line) => (
              <li className="pred-factors__item" key={line.feature}>
                <span className={`pred-factors__arrow pred-factors__arrow--${line.direction}`} aria-hidden="true">
                  {ARROW[line.direction]}
                </span>
                <span className="pred-factors__text">
                  <span className="ui-visually-hidden">{ARROW_LABEL[line.direction]}: </span>
                  {line.text}
                </span>
                {line.years && (
                  <span className={`pred-factors__years pred-factors__years--${line.direction}`}>
                    <span className="ui-visually-hidden">건강 나이 {line.yearsSpoken}</span>
                    <span aria-hidden="true">{line.years}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {hasYears && (
        <p className="pred-info">
          <span className="pred-info__icon" aria-hidden="true">i</span>
          <span>{YEARS_NOTICE}</span>
        </p>
      )}
      <p className="pred-info">
        <span className="pred-info__icon" aria-hidden="true">i</span>
        <span>{AGE_IN_SCORE_NOTICE}</span>
      </p>
    </section>
  )
}
