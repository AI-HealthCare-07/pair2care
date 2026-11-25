// frontend/src/pages/HomePage.tsx
// S-12 홈 (Figma M05). 순서: 인사 → 오늘의 한 가지 → 건강 나이(높은 쪽 하나) → 컨디션 → 오늘 할 챌린지(다음 챌린지 포함) → 식단 기록
//  - 건강 나이·컨디션은 Figma M05에 자리가 없어서 11/25 팀장님 순서로 넣음
//  - 🔔 알림(12장)·짝꿍 응원(8-12, P2)은 화면이 생기면 붙임
// 카드마다 따로 불러오고 따로 실패해서, 한 API가 안 돼도 나머지는 보임

import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import ConditionPicker from '../components/home/ConditionPicker'
import DailyActionCard from '../components/home/DailyActionCard'
import HealthAgeCard from '../components/home/HealthAgeCard'
import TodayChallenges from '../components/home/TodayChallenges'
import { homeDateLabel } from '../home/homeView'
import '../components/home/home.css'

export default function HomePage() {
  const { state } = useAuth()
  const nickname = state.status === 'authed' ? state.me.nickname : null

  return (
    <section className="home-page" aria-labelledby="home-title">
      <header>
        <p className="home-header__date">{homeDateLabel(new Date())}</p>
        <h1 id="home-title" className="home-header__title">
          {nickname ? `${nickname}님, 오늘도 반가워요` : '오늘도 반가워요'}
        </h1>
      </header>
      <DailyActionCard />
      <HealthAgeCard />
      <ConditionPicker />
      <TodayChallenges />
      <Link className="ui-btn ui-btn--secondary ui-btn--full home-meal" to="/records/meals">
        📷 오늘 식단 기록하기
      </Link>
    </section>
  )
}
