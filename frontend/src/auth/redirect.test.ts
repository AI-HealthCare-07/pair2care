// frontend/src/auth/redirect.test.ts
import { describe, expect, it } from 'vitest'
import { afterLoginPath, fromState } from './redirect'

describe('afterLoginPath', () => {
  it('원래 주소가 있으면 거기로 (쿼리 포함)', () => {
    expect(afterLoginPath('/records/meals?date=2026-11-25', true)).toBe('/records/meals?date=2026-11-25')
  })

  it('없으면 설문 여부로 홈 / 설문', () => {
    expect(afterLoginPath(undefined, true)).toBe('/home')
    expect(afterLoginPath(undefined, false)).toBe('/onboarding')
  })

  it('다른 사이트 주소·로그인 화면들·이상한 값은 무시', () => {
    expect(afterLoginPath('//evil.example.com', true)).toBe('/home')
    expect(afterLoginPath('https://evil.example.com', true)).toBe('/home')
    expect(afterLoginPath('/login', true)).toBe('/home')
    expect(afterLoginPath('/signup?x=1', false)).toBe('/onboarding')
    expect(afterLoginPath(42, true)).toBe('/home')
  })
})

describe('fromState', () => {
  it('state.from만 꺼냄', () => {
    expect(fromState({ from: '/my' })).toBe('/my')
    expect(fromState(null)).toBeUndefined()
    expect(fromState('x')).toBeUndefined()
  })
})
