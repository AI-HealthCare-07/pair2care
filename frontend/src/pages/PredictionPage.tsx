// frontend/src/pages/PredictionPage.tsx
// S-09 예측 결과 (/prediction, Figma M04·M04-b). 설문 저장 뒤 여기로 옴.
// 들어올 때마다 5-2를 부르고(설문에서 넘긴 state는 안 씀), 결과 카드마다 5-3으로 요인을 가져옴.
// 화면 상태 판단은 prediction/view.ts 한 곳에서 (일반 안내 / 예측 실패 / 결과).
//
// 1차 범위(팀장님 11/25): 질환 카드 · 관리 중 · 일반 안내 · 예측 실패.
// 12/4까지: 검진 기준표 줄 · 대사증후군 카드 · 빠진 검진 항목 → S-07 연결.
// 하단 버튼(챌린지 만들기 · 습관 바꾸면)은 화면이 생기면 붙임.
// 예측 실패 → "다시 계산하기"(5-5): 200·409면 5-2를 다시 부르고, 503·시간 초과면 실패 화면 그대로 + 안내.
//
// 개발용: VITE_USE_MOCK=true일 때 주소 뒤에 ?mock=failed 처럼 붙이면 가짜 응답 경우가 바뀜
//         (이름 목록: api/predictions.mockScenarios.ts. 다시 계산 성공은 failed, 또 실패는 failed_again)

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { PredictionDetail } from '../api/predictions'
import { predictionsApi } from '../api/predictionsApi'
import Button from '../components/common/Button'
import MedicalNotice from '../components/common/MedicalNotice'
import TopBar from '../components/common/TopBar'
import DiseaseCard from '../components/prediction/DiseaseCard'
import FactorsCard, { type FactorGroup } from '../components/prediction/FactorsCard'
import GeneralGuide from '../components/prediction/GeneralGuide'
import '../components/prediction/prediction.css'
import { FAILED_MESSAGE, FAILED_TITLE, RETRY_BUSY, RETRY_BUTTON, RETRY_FAILED_AGAIN } from '../prediction/labels'
import { buildPredictionView, factorLines, retryFailureAction, type PredictionView } from '../prediction/view'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; view: PredictionView; factorGroups: FactorGroup[] }

const HOME_PATH = '/home'

/** 결과 카드마다 5-3을 불러 요인을 모음. 하나가 실패해도 그 질환 요인만 빠지고 화면은 그대로 */
async function loadFactorGroups(view: PredictionView): Promise<FactorGroup[]> {
  if (view.kind !== 'RESULT') return []
  const resultCards = view.cards.filter((c) => c.kind === 'RESULT')
  const details = await Promise.allSettled(resultCards.map((c) => predictionsApi.getPrediction(c.model.id)))
  return resultCards.map((card, i) => {
    const settled = details[i]
    const detail: PredictionDetail | null = settled.status === 'fulfilled' ? settled.value : null
    return { disease: card.disease, lines: detail?.method === 'MODEL' ? factorLines(detail.factors) : [] }
  })
}

export default function PredictionPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const mockScenario = searchParams.get('mock')
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  // effect 안에서는 Promise 콜백에서만 setState (react-hooks/set-state-in-effect, MealsPage와 같은 방식)
  useEffect(() => {
    let ignore = false
    predictionsApi
      .setMockScenario(mockScenario)
      .then(() => predictionsApi.getLatestPredictions())
      .then(async (latest) => {
        const view = buildPredictionView(latest)
        const factorGroups = await loadFactorGroups(view)
        if (!ignore) setState({ status: 'ready', view, factorGroups })
      })
      .catch((err: unknown) => {
        if (ignore) return
        if (err instanceof ApiError && err.status === 404) {
          navigate('/onboarding', { replace: true }) // 5-2 404 = 아직 설문 기록이 없음
          return
        }
        // 401(세션 만료)은 화면에서 옮기지 않음: AuthProvider가 guest로 바뀌고 RequireAuth가 보던 화면(from)을 담아 /login으로 보냄 (#134)
        setState({ status: 'error', message: '위험도를 불러오지 못했어요. 인터넷 연결을 확인하고 다시 불러와 주세요.' })
      })
    return () => {
      ignore = true
    }
  }, [mockScenario, reloadKey, navigate])

  function reload() {
    setState({ status: 'loading' })
    setRetryError(null)
    setReloadKey((k) => k + 1)
  }

  // 5-5 다시 계산. 요청 중에는 버튼을 막음 (동시에 두 번 보내면 둘 다 저장될 수 있음, api.md 5-5)
  async function retry() {
    if (retrying) return
    setRetrying(true)
    setRetryError(null)
    try {
      await predictionsApi.retryPredictions()
      reload()
    } catch (err) {
      switch (retryFailureAction(err)) {
        case 'RELOAD':
          reload() // 409: 이미 계산돼 있음 → 결과를 다시 불러옴
          break
        case 'ONBOARDING':
          navigate('/onboarding', { replace: true })
          break
        case 'STAY_FAILED':
          setRetryError(RETRY_FAILED_AGAIN)
          break
      }
    } finally {
      setRetrying(false)
    }
  }

  const goHome = () => navigate(HOME_PATH)
  const isGeneral = state.status === 'ready' && state.view.kind === 'GENERAL'

  return (
    <div className="pred-screen">
      <TopBar title={isGeneral ? '건강 안내' : '나의 위험도'} onBack={goHome} />
      <main className="pred-body">
        {predictionsApi.isMock && (
          <p className="pred-dev">가짜 데이터 ({mockScenario ?? 'normal'}) · 주소 뒤 ?mock=이름 으로 바꿀 수 있어요</p>
        )}

        {state.status === 'loading' && (
          <p className="pred-status" role="status">
            위험도를 불러오고 있어요.
          </p>
        )}

        {state.status === 'error' && (
          <>
            <p className="pred-error" role="alert">
              {state.message}
            </p>
            <Button variant="secondary" fullWidth onClick={reload}>
              다시 불러오기
            </Button>
          </>
        )}

        {state.status === 'ready' && state.view.kind === 'GENERAL' && (
          <>
            <h2 className="pred-title">{'지금은 위험도 대신\n일반 건강 안내를 보여 드려요'}</h2>
            <GeneralGuide />
            <MedicalNotice />
          </>
        )}

        {state.status === 'ready' && state.view.kind === 'FAILED' && (
          <>
            <h2 className="pred-title">{FAILED_TITLE}</h2>
            <p className="pred-status">{FAILED_MESSAGE}</p>
            <MedicalNotice />
            <div className="pred-actions">
              {retryError && (
                <p className="pred-error" role="alert">
                  {retryError}
                </p>
              )}
              <Button fullWidth loading={retrying} onClick={() => void retry()}>
                {retrying ? RETRY_BUSY : RETRY_BUTTON}
              </Button>
              <Button variant="secondary" fullWidth onClick={goHome}>
                홈으로 가기
              </Button>
            </div>
          </>
        )}

        {state.status === 'ready' && state.view.kind === 'RESULT' && (
          <>
            <h2 className="pred-title">{'지금 생활습관을 기준으로\n계산한 참고값이에요'}</h2>
            {state.view.cards.map((card) => (
              <DiseaseCard key={card.disease} card={card} />
            ))}
            <FactorsCard groups={state.factorGroups} />
            <MedicalNotice />
          </>
        )}
      </main>
    </div>
  )
}
