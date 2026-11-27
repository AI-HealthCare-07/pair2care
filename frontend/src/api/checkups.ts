// frontend/src/api/checkups.ts
// 4장 검진 수치 (api.md 4-1). 지금은 S-07 저장만. 목록·수정·삭제(4-2·4-4·4-5)는 마이 수정 화면 만들 때

import { apiFetch, toApiError } from './client'
import type { CheckupValues } from '../checkup/checkupFields'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

export interface SavedCheckup {
  predictionError: boolean // true면 검진은 저장됐고 예측만 실패 (4-1)
}

/** 4-1 저장 → 서버가 예측을 다시 계산. 400은 ApiError(서버 문구) */
export async function createCheckup(checkedOn: string, values: CheckupValues): Promise<SavedCheckup> {
  if (useMock) return { predictionError: false }
  const res = await apiFetch('/checkup-records', {
    method: 'POST',
    body: JSON.stringify({ checked_on: checkedOn, ...values }),
  })
  if (!res.ok) throw await toApiError(res)
  const body = (await res.json()) as { prediction_error?: boolean }
  return { predictionError: body.prediction_error === true }
}
