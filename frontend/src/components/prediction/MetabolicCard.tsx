// frontend/src/components/prediction/MetabolicCard.tsx
// 대사증후군 카드 (wireframe.md S-09, api.md 5-1). 5-2 metabolic_syndrome으로 그림, null이면 페이지에서 안 그림.
// 해당 / 해당 아님 / 판단 어려움. 판단 어려움은 첫 빠진 항목의 S-07 입력칸으로 링크 (#153 ?focus=)
// 배지 색: 해당 = 높음 색, 해당 아님 = 낮음 색, 판단 어려움 = 회색 (색과 글자를 같이 보여 줌)

import { Link } from 'react-router-dom'
import { METABOLIC_BADGE, METABOLIC_INFO, METABOLIC_TITLE, metabolicMessage } from '../../prediction/labels'
import { checkupLink, type MetabolicView } from '../../prediction/view'
import './prediction.css'

const BADGE_CLASS = { MET: 'HIGH', NOT_MET: 'LOW', UNKNOWN: 'MANAGED' } as const

export default function MetabolicCard({ metabolic }: { metabolic: MetabolicView }) {
  const { status, metCount, missingLabels, focus } = metabolic
  const message = metabolicMessage(status, metCount, missingLabels)

  return (
    <section className="pred-card" aria-labelledby="pred-metabolic-title">
      <div className="pred-card__head">
        <h3 className="pred-card__name" id="pred-metabolic-title">
          {METABOLIC_TITLE}
        </h3>
        <span className={`pred-badge pred-badge--${BADGE_CLASS[status]}`}>{METABOLIC_BADGE[status]}</span>
      </div>

      {focus ? (
        <Link className="pred-link pred-link--block" to={checkupLink(focus)}>
          {message}
          <span className="pred-link__chevron" aria-hidden="true">›</span>
        </Link>
      ) : (
        <p className="pred-card__note">{message}</p>
      )}

      <p className="pred-info">
        <span className="pred-info__icon" aria-hidden="true">
          i
        </span>
        <span>{METABOLIC_INFO}</span>
      </p>
    </section>
  )
}
