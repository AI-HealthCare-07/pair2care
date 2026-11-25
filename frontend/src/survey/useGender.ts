// frontend/src/survey/useGender.ts
// 설문 화면이 쓰는 사용자 성별. 성별을 모르면 임신 문항(여성만)과 13번 성별 문구를 정할 수 없어서
// 성별을 받은 뒤에 문항 흐름을 시작함.
//  - 진짜 모드: 인증 가드(#116)가 앱 켜질 때 받아 둔 내 정보(useAuth의 state.me.gender). /users/me를 따로 부르지 않음
//  - 가짜 모드(VITE_USE_MOCK=true): 주소의 ?gender=FEMALE 로 바꿔 볼 수 있음 (기본 MALE, 여성 문항 확인용)
// /onboarding은 가드 안이라 여기 올 때는 로그인 상태. 로그인이 풀리면 가드가 /login으로 보냄

import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import type { Gender } from './types'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

export function useGender(): { gender: Gender | undefined; error: string | null } {
  const { state } = useAuth()
  const [params] = useSearchParams()

  if (useMock) return { gender: params.get('gender') === 'FEMALE' ? 'FEMALE' : 'MALE', error: null }
  if (state.status !== 'authed') return { gender: undefined, error: null } // 가드가 처리하는 중 (보통 안 옴)
  const { gender } = state.me
  if (gender !== 'MALE' && gender !== 'FEMALE') return { gender: undefined, error: '성별 정보를 확인하지 못했어요.' }
  return { gender, error: null }
}
