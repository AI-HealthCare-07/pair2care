// frontend/src/api/consents.ts
// 2-6 동의 내역. 마이에서 선택 동의 MODEL_IMPROVEMENT 켜기·끄기에 씀

import { apiFetch, toApiError } from './client'
import { TERMS_VERSION, type Agreement } from './auth'

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

export interface ConsentStatus {
  agreement: Agreement
  version: string | null      // 한 번도 답하지 않은 선택 동의는 null
  is_agreed: boolean
  agreed_at: string | null
  current_version: string
}

/** 2-6 GET: 4종 현재 상태 */
export async function getConsents(): Promise<ConsentStatus[]> {
  if (useMock) return []
  const res = await apiFetch('/users/me/consents')
  if (!res.ok) throw await toApiError(res)
  return ((await res.json()) as { items: ConsentStatus[] }).items
}

/** 2-6 POST: 새 행을 쌓음. 필수 동의 철회는 400 (탈퇴로 안내) */
export async function saveConsent(agreement: Agreement, isAgreed: boolean): Promise<ConsentStatus> {
  const body = { agreement, version: TERMS_VERSION, is_agreed: isAgreed }
  if (useMock) return { ...body, agreed_at: null, current_version: TERMS_VERSION }
  const res = await apiFetch('/users/me/consents', { method: 'POST', body: JSON.stringify(body) })
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as ConsentStatus
}
