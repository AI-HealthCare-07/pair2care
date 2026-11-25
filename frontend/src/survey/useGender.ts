// frontend/src/survey/useGender.ts
// 설문 화면이 쓰는 사용자 성별. 성별을 모르면 임신 문항(여성만)과 13번 성별 문구를 정할 수 없어서
// 성별을 받은 뒤에 문항 흐름을 시작함.
//  - 가짜 모드(VITE_USE_MOCK=true): 주소의 ?gender=FEMALE 로 바꿔 볼 수 있음 (기본 MALE)
//  - 진짜 모드: GET /users/me (api.md 2-5). 가입 응답에는 user.gender가 있지만 로그인 응답에는 없어서 users/me로 통일
//  - 로그인이 풀려 있으면(401, 토큰 갱신도 실패) 로그인 화면으로 보냄 (인증 가드가 생기기 전까지의 안전장치)
// ⚠️ 임시: 로그인 사용자 정보를 보관하는 곳(팀장님 후속 PR)이 생기면 이 파일의 fetchMyGender 대신 거기서 gender를 읽음.
//    users/me를 부르는 코드가 이 파일 안에만 있어서(별도 api/users.ts 없음) 그 PR과 파일이 겹치지 않음.

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, ApiError, toApiError } from '../api/client'
import type { Gender } from './types'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

async function fetchMyGender(): Promise<Gender | undefined> {
  const res = await apiFetch('/users/me')
  if (!res.ok) throw await toApiError(res)
  const body = (await res.json()) as { gender?: unknown }
  return body.gender === 'MALE' || body.gender === 'FEMALE' ? body.gender : undefined
}

type Fetched = { gender: Gender | undefined } | { error: string }

export function useGender(): { gender: Gender | undefined; error: string | null } {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [fetched, setFetched] = useState<Fetched | null>(null)

  useEffect(() => {
    if (useMock) return
    let ignore = false
    fetchMyGender()
      .then((gender) => {
        if (!ignore) setFetched({ gender })
      })
      .catch((err: unknown) => {
        if (ignore) return
        if (err instanceof ApiError && err.status === 401) {
          navigate('/login', { replace: true })
          return
        }
        setFetched({ error: '내 정보를 불러오지 못했어요.' })
      })
    return () => {
      ignore = true
    }
  }, [navigate])

  if (useMock) return { gender: params.get('gender') === 'FEMALE' ? 'FEMALE' : 'MALE', error: null }
  if (fetched && 'error' in fetched) return { gender: undefined, error: fetched.error }
  if (fetched && fetched.gender === undefined) return { gender: undefined, error: '성별 정보를 확인하지 못했어요.' }
  return { gender: fetched?.gender, error: null }
}
