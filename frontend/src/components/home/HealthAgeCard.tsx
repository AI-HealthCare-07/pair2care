// frontend/src/components/home/HealthAgeCard.tsx
// 홈 건강 나이 한 줄 (S-12, 11/25 결정: 높은 쪽 하나·진단받은 질환 숨김). Figma M05에는 자리가 없어서 오늘의 한 가지 아래에 둠
// 5-2를 못 읽거나(설문 전 404 포함) 보여 줄 건강 나이가 없으면 카드 자체를 숨김 → 홈의 다른 카드는 그대로
// 불러오는 동안은 같은 크기로 자리를 잡아 둬서 아래 카드가 밀리지 않게 함 (#119 리뷰)

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { predictionsApi } from '../../api/predictionsApi'
import { pickHomeHealthAge, type HomeHealthAge } from '../../home/homeView'
import { DISEASE_LABEL } from '../../prediction/labels'

export default function HealthAgeCard() {
  const [picked, setPicked] = useState<HomeHealthAge | null | 'loading'>('loading')

  useEffect(() => {
    let ignore = false
    predictionsApi
      .getLatestPredictions()
      .then((latest) => {
        if (!ignore) setPicked(pickHomeHealthAge(latest))
      })
      .catch(() => {
        if (!ignore) setPicked(null)
      })
    return () => {
      ignore = true
    }
  }, [])

  if (picked === 'loading')
    return (
      <section className="home-card home-card--age" aria-busy="true" aria-label="건강 나이">
        <p className="home-card__eyebrow">건강 나이</p>
        <p className="home-age__level home-placeholder" aria-hidden="true">
          &nbsp;
        </p>
        <p className="home-muted" role="status">
          불러오고 있어요.
        </p>
        <span className="home-link home-placeholder" aria-hidden="true">
          &nbsp;
        </span>
      </section>
    )
  if (!picked) return null
  return (
    <section className="home-card home-card--age" aria-labelledby="home-age-title">
      <h2 id="home-age-title" className="home-card__eyebrow">
        {DISEASE_LABEL[picked.disease]} 건강 나이
      </h2>
      <p className="home-age__level">{picked.line.level}</p>
      <p className="home-muted">{picked.line.compareText}</p>
      <Link className="home-link" to="/prediction">
        위험도 자세히 보기
      </Link>
    </section>
  )
}
