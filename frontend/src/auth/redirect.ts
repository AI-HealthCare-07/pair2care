// frontend/src/auth/redirect.ts
// 로그인 뒤 어디로 보낼지. 가드가 /login으로 보낼 때 원래 주소를 state.from에 넣어 둠

const AUTH_PAGES = new Set(['/', '/login', '/signup'])

/**
 * 원래 보려던 주소가 있으면 거기로, 없으면 설문 여부로 홈 / 설문.
 * from은 우리 앱 안 주소(`/`로 시작, `//`로 시작하는 다른 사이트 주소는 안 됨)일 때만 씀.
 * 설문 전인데 from이 /home이어도 괜찮음: 가드가 다시 /onboarding으로 보냄
 */
export function afterLoginPath(from: unknown, hasHealthProfile: boolean): string {
  if (typeof from === 'string' && from.startsWith('/') && !from.startsWith('//')) {
    const pathname = from.split(/[?#]/)[0]
    if (!AUTH_PAGES.has(pathname)) return from
  }
  return hasHealthProfile ? '/home' : '/onboarding'
}

/** location.state에서 from 꺼내기 (모양이 다르면 undefined) */
export function fromState(state: unknown): unknown {
  return typeof state === 'object' && state !== null && 'from' in state ? (state as { from: unknown }).from : undefined
}
