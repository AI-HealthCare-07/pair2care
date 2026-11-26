// frontend/src/components/record/RecordTabs.tsx
// 기록 화면 맨 위 항목 탭 (혈압·혈당·체중·걸음·운동·음주·식단, Figma M07·M07-b)
// 가로 스크롤 탭. 화면을 열면 선택된 탭이 보이게 자동으로 스크롤함 (식단 탭으로 들어오면 맨 끝이 보임, M07 메모)

import { useEffect, useRef } from 'react'
import { NavLink } from 'react-router-dom'
import { MEALS_TAB, RECORD_TYPES } from '../../records/recordTypes'
import './record.css'

const TABS = [...RECORD_TYPES.map((type) => ({ kind: type.kind, tab: type.tab, path: `/records/${type.kind}` })), MEALS_TAB]

export default function RecordTabs() {
  const listRef = useRef<HTMLElement>(null)

  useEffect(() => {
    // 선택된 탭(aria-current="page")을 가운데쯤으로 (처음 한 번, 애니메이션 없이)
    listRef.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [])

  return (
    <nav ref={listRef} className="record-tabs" aria-label="기록 항목">
      {TABS.map((tab) => (
        <NavLink key={tab.kind} to={tab.path} end className={({ isActive }) => `record-tab${isActive ? ' record-tab--active' : ''}`}>
          {tab.tab}
        </NavLink>
      ))}
    </nav>
  )
}
