// frontend/src/components/prediction/DiseaseCard.tsx
// S-09 질환 카드 하나 (Figma M04): 결과 / 관리 중 / 계산 못 함.
// 결과 카드: 이름 · 단계 배지 · 게이지(점수 위치) · 낮음·주의·높음 · 단계별 한 줄 · 건강 나이 한 줄.
// 점수 숫자는 Figma처럼 화면에 안 쓰고 스크린리더만 읽음. 단계는 색과 글자를 같이 보여 줌 (색만으로 구분 X).
// 검진 기준표 줄(12/4): 기준표 행이 있으면 카드 아래쪽에 "검진 수치(날짜) 기준: 혈압이 주의 범위예요" + 주의·높음은 병원 확인 권유.
//   없으면 S-07 링크(유효한 검진 없음 / 이 질환 항목이 빠짐). 모델 점수와 섞이지 않게 선으로 나눔 (wireframe.md S-09)

import { Link } from 'react-router-dom'
import { healthAgeLine } from '../../prediction/healthAge'
import {
  CHECKUP_ADVICE,
  CHECKUP_PROMPT_TEXT,
  CHECKUP_RANGE_TEXT,
  checkupHeading,
  DISEASE_LABEL,
  LEVEL_LABEL,
  LEVEL_MESSAGE,
  MANAGED_MESSAGE,
  MANAGED_TITLE,
  MISSING_MESSAGE,
} from '../../prediction/labels'
import {
  CAUTION_MIN_SCORE,
  checkupLink,
  GAUGE_LABEL_PERCENT,
  gaugePercent,
  HIGH_MIN_SCORE,
  type DiseaseCard as DiseaseCardData,
} from '../../prediction/view'
import './prediction.css'

interface Props {
  card: DiseaseCardData
  checkedOn?: string | null // 기준표 행의 검진 날짜 (5-3 checked_on). 못 불러오면 null → 날짜 없이
}

export default function DiseaseCard({ card, checkedOn = null }: Props) {
  const name = DISEASE_LABEL[card.disease]
  const headingId = `pred-card-${card.disease}`

  if (card.kind === 'MANAGED') {
    return (
      <section className="pred-card" aria-labelledby={headingId}>
        <div className="pred-card__head">
          <h3 className="pred-card__name" id={headingId}>{name}</h3>
          <span className="pred-badge pred-badge--MANAGED">{MANAGED_TITLE}</span>
        </div>
        <p className="pred-card__note">{MANAGED_MESSAGE}</p>
      </section>
    )
  }

  if (card.kind === 'MISSING') {
    return (
      <section className="pred-card" aria-labelledby={headingId}>
        <div className="pred-card__head">
          <h3 className="pred-card__name" id={headingId}>{name}</h3>
        </div>
        <p className="pred-card__note">{MISSING_MESSAGE}</p>
      </section>
    )
  }

  const { level, score, health_age } = card.model
  const percent = gaugePercent(score)
  const age = healthAgeLine(health_age)

  return (
    <section className="pred-card" aria-labelledby={headingId}>
      <div className="pred-card__head">
        <h3 className="pred-card__name" id={headingId}>{name}</h3>
        <span className={`pred-badge pred-badge--${level}`}>{LEVEL_LABEL[level]}</span>
      </div>

      {percent !== null && (
        <div className="pred-gauge" role="img" aria-label={`위험도 ${score}점, ${LEVEL_LABEL[level]}`}>
          <div className="pred-gauge__track">
            {/* 단계 구분선 30 · 60 */}
            <span className="pred-gauge__divider" style={{ left: `${CAUTION_MIN_SCORE}%` }} />
            <span className="pred-gauge__divider" style={{ left: `${HIGH_MIN_SCORE}%` }} />
            <span className={`pred-gauge__marker pred-gauge__marker--${level}`} style={{ left: `${percent}%` }} />
          </div>
          {/* 글자는 단계 구간 가운데 (15 · 45 · 80%) */}
          <div className="pred-gauge__labels" aria-hidden="true">
            {(['LOW', 'CAUTION', 'HIGH'] as const).map((key) => (
              <span key={key} style={{ left: `${GAUGE_LABEL_PERCENT[key]}%` }}>
                {LEVEL_LABEL[key]}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className={`pred-card__message pred-card__message--${level}`}>{LEVEL_MESSAGE[level]}</p>

      {age && (
        <p className="pred-card__note">
          건강 나이 <strong>{age.level}</strong> · {age.compareText}
        </p>
      )}

      {card.checkup && (
        <div className="pred-checkup">
          <p className="pred-checkup__heading">{checkupHeading(checkedOn)}</p>
          <p className={`pred-checkup__range pred-checkup__range--${card.checkup.level}`}>
            {CHECKUP_RANGE_TEXT[card.disease][card.checkup.level]}
          </p>
          {/* 병원 권유는 주의·높음만. 모델도 높음이면 위 한 줄에 이미 있어서 같은 말을 두 번 하지 않음 */}
          {card.checkup.level !== 'LOW' && level !== 'HIGH' && <p className="pred-card__note">{CHECKUP_ADVICE}</p>}
        </div>
      )}

      {card.prompt && (
        <div className="pred-checkup">
          <Link className="pred-link" to={checkupLink(card.prompt.focus)}>
            {CHECKUP_PROMPT_TEXT[card.prompt.kind]}
            <span className="pred-link__chevron" aria-hidden="true">›</span>
          </Link>
        </div>
      )}
    </section>
  )
}
