import { NavLink } from 'react-router-dom'
import { ChallengeIcon, HomeIcon, MyIcon, PairIcon, RecordIcon } from './NavIcons'
import './BottomNav.css'

const TABS = [
  { to: '/home', label: '홈', Icon: HomeIcon },
  { to: '/challenges', label: '챌린지', Icon: ChallengeIcon },
  { to: '/pairs', label: '짝꿍', Icon: PairIcon },
  { to: '/records', label: '기록', Icon: RecordIcon },
  { to: '/my', label: '마이', Icon: MyIcon },
]

export default function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="하단 메뉴">
      {TABS.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => (isActive ? 'tab tab--active' : 'tab')}
        >
          <Icon />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}