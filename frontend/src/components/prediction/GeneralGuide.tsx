// frontend/src/components/prediction/GeneralGuide.tsx
// M04-b 일반 안내 (위험도 계산 제외: 임신 중 · 만 30~69세 밖, api.md 5-0 skipped_reason). 문구는 Figma M04-b 그대로.
// 하단 "건강 습관 챌린지 만들기" 버튼은 챌린지 만들기 화면이 생기면 붙임 (팀장님 11/25: 화면 전까지 숨김)

import './prediction.css'

const TIPS = ['걷기처럼 가벼운 운동을 주 3회 이상', '국·찌개 국물은 덜 먹기', '1년에 한 번 혈압·혈당 재 보기']

export default function GeneralGuide() {
  return (
    <section className="pred-card" aria-labelledby="pred-guide-title">
      <h3 className="pred-guide__title" id="pred-guide-title">이렇게 관리해 보세요</h3>
      <ul className="pred-guide__list">
        {TIPS.map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ul>
      <p className="pred-info">
        <span className="pred-info__icon" aria-hidden="true">i</span>
        <span>
          임신 중이거나 만 30~69세가 아니면 위험도 계산식이 맞지 않아 점수를 보여 드리지 않아요. 임신 중이라면 담당
          의료진과 먼저 상의해 주세요.
        </span>
      </p>
    </section>
  )
}
