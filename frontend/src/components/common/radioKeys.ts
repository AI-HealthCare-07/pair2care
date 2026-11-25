// frontend/src/components/common/radioKeys.ts
// 라디오 그룹 방향키 (WAI-ARIA): ↑↓←→로 앞뒤, Home·End로 처음·끝. 옮기면 바로 선택하는 건 부르는 쪽이 함
// 설문 보기(OptionList)·가입 성별 칩이 같이 씀

import type { KeyboardEvent } from 'react'

/** 방향키면 옮겨 갈 보기 번호를 돌려주고 포커스도 옮김. 다른 키면 null */
export function moveRadioFocus(e: KeyboardEvent<HTMLElement>): number | null {
  const buttons = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]'))
  const current = buttons.findIndex((b) => b === document.activeElement)
  if (current < 0) return null

  let next: number | null = null
  if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = (current + 1) % buttons.length
  else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = (current - 1 + buttons.length) % buttons.length
  else if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = buttons.length - 1
  if (next === null) return null

  e.preventDefault()
  buttons[next].focus()
  return next
}
