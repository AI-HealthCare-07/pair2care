// frontend/src/components/common/ChallengeRow.tsx
// 챌린지 한 줄. Figma 컴포넌트 시트 "ChallengeRow": Title / Sub / Meta, 체크 원 40px 터치 영역
//  예) title="점심 후 10분 걷기"  sub="이번 주 2/3회"  meta="🔥 4일"
//  M21 목록처럼 쓸 때: sub="주 3회 · 민수님과 · 연속 2주"  meta="2/3"
//  - 원: onToggle이 있으면 체크 버튼, 없으면 그림만
//  - 본문: onOpen이 있으면 누를 수 있는 영역 (상세로 이동 등). 원과 본문은 서로 다른 버튼이라 중첩되지 않음
// ⚠️ 원을 눌러 체크하는지, 줄 전체가 상세 이동인지는 화면 Figma로 확인 필요 (둘 다 열어 둠)

import type { ReactNode } from 'react'
import './common.css'

interface Props {
  title: string
  sub?: string
  /** 오른쪽 작은 정보 (🔥 4일, 2/3 등) */
  meta?: ReactNode
  checked?: boolean
  onToggle?: () => void
  onOpen?: () => void
}

function CheckCircle({ checked }: { checked: boolean }) {
  return (
    <span className={`ui-row__circle${checked ? ' is-checked' : ''}`} aria-hidden="true">
      {checked && (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      )}
    </span>
  )
}

export default function ChallengeRow({ title, sub, meta, checked = false, onToggle, onOpen }: Props) {
  const body = (
    <>
      <span className="ui-row__text">
        <span className="ui-row__title">{title}</span>
        {sub && <span className="ui-row__sub">{sub}</span>}
      </span>
      {meta != null && <span className={`ui-row__meta${checked ? ' is-checked' : ''}`}>{meta}</span>}
    </>
  )

  return (
    <div className="ui-row">
      {onToggle ? (
        <button type="button" className="ui-row__toggle" onClick={onToggle} aria-pressed={checked} aria-label={`${title} 체크`}>
          <CheckCircle checked={checked} />
        </button>
      ) : (
        <CheckCircle checked={checked} />
      )}
      {onOpen ? (
        <button type="button" className="ui-row__body" onClick={onOpen}>
          {body}
        </button>
      ) : (
        <div className="ui-row__body">{body}</div>
      )}
    </div>
  )
}
