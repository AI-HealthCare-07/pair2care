// frontend/src/pages/MealPickPage.tsx
// S-22 음식 고르기 (Figma M10) · REQ-FOOD-001·002 · api.md 10-2, 10-4, 10-5, 10-6, 10-8
// 흐름: 분석 중 → (완료) 후보 5개에서 고르기 / (실패) 다시 분석 · 직접 고르기(C-02) → PATCH → S-23

import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { mealsApi } from '../api/mealsApi'
import { MealApiError, type Food, type MealCandidate, type MealDetail, type Portion, type ServingUnit } from '../api/meals'
import Button from '../components/common/Button'
import TopBar from '../components/common/TopBar'
import CandidateCard from '../components/meal/CandidateCard'
import FoodSearch from '../components/meal/FoodSearch'
import MealPhoto from '../components/meal/MealPhoto'
import MedicalNotice from '../components/meal/MedicalNotice'
import PortionChips from '../components/meal/PortionChips'
import { servingText } from '../components/meal/mealFormat'
import { afterSavePath } from '../components/meal/mealSlots'
import '../components/meal/meal.css'

/** 화면에서 고른 음식 (후보·직접 검색·이미 저장된 음식 모두 이 모양으로 맞춤) */
interface Choice {
  food_id: number
  label: string
  serving_size: number
  serving_unit: ServingUnit
  kcal: number | null
}

const fromCandidate = (c: MealCandidate): Choice => ({
  food_id: c.food_id,
  label: c.model_label,
  serving_size: c.serving_size,
  serving_unit: c.serving_unit,
  kcal: c.kcal,
})

const fromFood = (f: Food): Choice => ({
  food_id: f.id,
  label: f.model_label,
  serving_size: f.serving_size,
  serving_unit: f.serving_unit,
  kcal: f.kcal,
})

const MAX_RETRY = 3 // api.md 10-6: retry_count 3 이상이면 429

export default function MealPickPage() {
  const { id } = useParams()
  const mealId = Number(id)
  const navigate = useNavigate()

  const [meal, setMeal] = useState<MealDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // 사용자가 직접 바꾼 값만 따로 저장. 안 바꿨으면 서버 값(후보 1번·저장된 인분)을 그대로 씀
  const [userChoice, setUserChoice] = useState<Choice | null>(null)
  const [userPortion, setUserPortion] = useState<Portion | null>(null)
  const [searching, setSearching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setMeal(await mealsApi.getMeal(mealId))
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof MealApiError ? err.message : '식단을 불러오지 못했어요.')
    } finally {
      setLoading(false)
    }
  }, [mealId])

  // 첫 조회: effect 안에서 setState를 바로 부르지 않고 Promise 콜백에서 부름 (react-hooks/set-state-in-effect)
  useEffect(() => {
    let ignore = false
    mealsApi
      .getMeal(mealId)
      .then((res) => {
        if (ignore) return
        setMeal(res)
        setLoadError(null)
      })
      .catch((err) => {
        if (!ignore) setLoadError(err instanceof MealApiError ? err.message : '식단을 불러오지 못했어요.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [mealId])

  // 분석 중이면 2초마다 다시 조회.
  // 임시 방식: api.md 10-2는 공통 SSE(12-6)의 task 이벤트를 받고 10-4를 다시 조회하라고 함.
  // SSE 훅이 생기면 이 effect를 이벤트 수신으로 바꾸면 됨 (조회 함수 load는 그대로 사용).
  const waiting = meal?.status === 'PENDING' || meal?.status === 'PROCESSING'
  useEffect(() => {
    if (!waiting) return
    const timer = setInterval(() => void load(), 2000)
    return () => clearInterval(timer)
  }, [waiting, load])

  function goBack() {
    navigate('/records/meals')
  }

  async function handleRetry() {
    setBusy(true)
    setActionError(null)
    try {
      await mealsApi.retryMeal(mealId)
    } catch (err) {
      // 429(3번 초과) · 409(상태 아님) · 503(큐 실패): 안내만 하고 최신 상태를 다시 받음
      setActionError(err instanceof MealApiError ? err.message : '다시 분석하지 못했어요.')
    } finally {
      await load()
      setBusy(false)
    }
  }

  async function handleSave(choice: Choice, portion: number) {
    setBusy(true)
    setActionError(null)
    try {
      await mealsApi.updateMeal(mealId, { food_id: choice.food_id, portion: portion as Portion })
      navigate(afterSavePath(mealId))
    } catch (err) {
      setActionError(err instanceof MealApiError ? err.message : '저장하지 못했어요. 잠시 후 다시 시도해 주세요.')
      if (err instanceof MealApiError && err.status === 409) void load() // 아직 분석 중
    } finally {
      setBusy(false)
    }
  }

  // ───── 불러오기 전·실패 ─────
  if (!Number.isInteger(mealId) || loadError || !meal) {
    return (
      <div className="meal-screen">
        <TopBar title="음식 고르기" onBack={goBack} />
        <div className="meal-screen__body">
          {loading && !loadError && Number.isInteger(mealId) ? (
            <p className="meal-status">불러오는 중이에요.</p>
          ) : (
            <p className="meal-status meal-status--error" role="alert">
              {loadError ?? '식단을 찾을 수 없어요.'}
            </p>
          )}
        </div>
      </div>
    )
  }

  // ───── 선택 상태 계산 ─────
  const candidates = meal.candidates ?? []
  const saved: Choice | null = meal.food
    ? (() => {
        const hit = candidates.find((c) => c.food_id === meal.food!.id)
        return hit
          ? fromCandidate(hit)
          : { food_id: meal.food!.id, label: meal.food!.model_label, serving_size: meal.food!.serving_size, serving_unit: meal.food!.serving_unit, kcal: null }
      })()
    : null
  // 화면은 후보 첫 번째를 미리 선택해 보여 줌 (저장은 PATCH 때, api.md 10-4)
  const selected: Choice | null = userChoice ?? saved ?? (candidates[0] ? fromCandidate(candidates[0]) : null)
  const portion = userPortion ?? meal.portion
  const isExtra = selected !== null && !candidates.some((c) => c.food_id === selected.food_id)
  const canRetry = meal.retry_count < MAX_RETRY

  const showPicker = meal.status === 'COMPLETED' || meal.status === 'FAILED'

  return (
    <div className="meal-screen">
      <TopBar title="음식 고르기" onBack={goBack} />

      <div className="meal-screen__body">
        <MealPhoto key={meal.image_url} src={meal.image_url} />

        {/* 분석 중 (PENDING·PROCESSING) */}
        {waiting && (
          <div className="meal-wait" role="status">
            <p className="meal-wait__title">사진을 분석하고 있어요</p>
            <p className="meal-wait__desc">끝나면 후보가 여기에 나타나요. 잠시만 기다려 주세요.</p>
          </div>
        )}

        {/* 분석 실패 (C-02) */}
        {meal.status === 'FAILED' && (
          <div className="meal-wait">
            <p className="meal-wait__title">사진을 분석하지 못했어요</p>
            <p className="meal-wait__desc">
              {canRetry ? '다시 분석하거나, 목록에서 직접 골라 주세요.' : '분석은 3번까지 할 수 있어요. 직접 골라 주세요.'}
            </p>
            {canRetry && (
              <Button variant="secondary" fullWidth className="meal-mt-16" onClick={handleRetry} loading={busy}>
                {busy ? '다시 분석하는 중이에요' : '다시 분석하기'}
              </Button>
            )}
          </div>
        )}

        {/* 후보 5개 */}
        {meal.status === 'COMPLETED' && (
          <>
            <h2 className="meal-section">어떤 음식인가요?</h2>
            <p className="meal-section__desc">AI가 고른 후보예요. 가능성 높은 순서예요. 맞는 걸 눌러 주세요.</p>
          </>
        )}

        {showPicker && (
          <div className="meal-candidates" role="radiogroup" aria-label="음식 후보">
            {isExtra && selected && (
              <CandidateCard
                label={selected.label}
                detail={servingText(selected.serving_size, selected.serving_unit, selected.kcal)}
                selected
                tag="직접 고른 음식"
                onSelect={() => undefined}
              />
            )}
            {candidates.map((c) => (
              <CandidateCard
                key={c.food_id}
                label={c.model_label}
                detail={servingText(c.serving_size, c.serving_unit, c.kcal)}
                selected={selected?.food_id === c.food_id}
                onSelect={() => setUserChoice(fromCandidate(c))}
              />
            ))}
          </div>
        )}

        {/* 직접 검색 (10-8) */}
        {showPicker &&
          (searching ? (
            <FoodSearch
              onSelect={(f) => {
                setUserChoice(fromFood(f))
                setSearching(false)
              }}
              onClose={() => setSearching(false)}
            />
          ) : (
            <button type="button" className="meal-link" onClick={() => setSearching(true)}>
              {meal.status === 'FAILED' ? '직접 고르기' : '목록에 없어요 → 직접 검색하기'}
            </button>
          ))}

        {/* 인분 + 저장 */}
        {showPicker && selected && (
          <>
            <h2 className="meal-section">얼마나 드셨어요?</h2>
            <PortionChips value={portion} onChange={setUserPortion} />
            <Button fullWidth className="meal-mt-24" onClick={() => handleSave(selected, portion)} loading={busy}>
              {busy ? '저장하고 있어요' : '영양 분석 보기'}
            </Button>
          </>
        )}

        {actionError && (
          <p className="meal-status meal-status--error" role="alert">
            {actionError}
          </p>
        )}

        <MedicalNotice />
      </div>
    </div>
  )
}
