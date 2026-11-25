// frontend/src/pages/MealsPage.tsx
// S-21 기록 > 식단 탭 (Figma M07-b) · REQ-FOOD-001 · api.md 10-1, 10-3
// ⚠️ 기록 화면의 탭(혈압·혈당·…·식단)은 RecordsPage 담당 영역이라 여기엔 넣지 않았음.
//    탭이 생기면 아래 <section> 안쪽(카드)만 식단 탭 안으로 옮기면 됨.

import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { mealsApi } from '../api/mealsApi'
import { MealApiError, type MealListResponse } from '../api/meals'
import Button from '../components/common/Button'
import MedicalNotice from '../components/common/MedicalNotice'
import {
  DAILY_KCAL,
  firstEmptySlot,
  formatMonthDay,
  mealRoute,
  rowSummary,
  slotOf,
  todayKst,
} from '../components/meal/mealSlots'
import '../components/meal/meal.css'

// api.md 10-1: jpg / png / webp, 최대 10MB (정할 것 16번 제안값)
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

export default function MealsPage() {
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)

  // 가짜 모드(VITE_USE_MOCK=true)면 가짜 데이터가 들어 있는 날짜, 아니면 오늘(KST)
  const [date] = useState(() => mealsApi.demoDate ?? todayKst())
  const [data, setData] = useState<MealListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await mealsApi.listMeals(date))
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof MealApiError ? err.message : '식단을 불러오지 못했어요.')
    } finally {
      setLoading(false)
    }
  }, [date])

  // 첫 조회: effect 안에서 setState를 바로 부르지 않고 Promise 콜백에서 부름 (react-hooks/set-state-in-effect)
  useEffect(() => {
    let ignore = false
    mealsApi
      .listMeals(date)
      .then((res) => {
        if (ignore) return
        setData(res)
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
  }, [date])

  function retryLoad() {
    setLoading(true)
    void load()
  }

  function openPicker() {
    setUploadError(null)
    fileRef.current?.click()
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // 같은 사진을 다시 골라도 change가 일어나도록
    if (!file) return
    if (!IMAGE_TYPES.includes(file.type)) {
      setUploadError('jpg, png, webp 사진만 올릴 수 있어요.')
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setUploadError('사진은 10MB까지 올릴 수 있어요.')
      return
    }

    setUploading(true)
    setUploadError(null)
    try {
      const res = await mealsApi.uploadMeal(file)
      navigate(`/records/meals/${res.meal_id}`) // S-22에서 분석 결과를 기다림
    } catch (err) {
      if (err instanceof MealApiError) {
        setUploadError(err.message)
        // 503: 기록은 FAILED로 남아 있으므로 목록을 다시 불러와 보여 줌 (api.md 10-1)
        if (err.status === 503) void load()
      } else {
        setUploadError('사진을 올리지 못했어요. 잠시 후 다시 시도해 주세요.')
      }
    } finally {
      setUploading(false)
    }
  }

  const items = data?.items ?? []
  const totalKcal = data?.daily_total.kcal ?? 0
  const percent = Math.min(100, (totalKcal / DAILY_KCAL) * 100)
  const emptySlot = firstEmptySlot(items)

  return (
    <div className="meal-page">
      <h1 className="meal-page__title">기록</h1>

      <section className="meal-card" aria-labelledby="meal-today-title">
        <div className="meal-card__head">
          <h2 className="meal-card__title" id="meal-today-title">
            오늘 식단 · {formatMonthDay(date)}
          </h2>
          <span className="meal-card__hint">사진 3장까지</span>
        </div>

        <div className="meal-total">
          <div>
            <span className="meal-total__value">{Math.round(totalKcal)}</span>
            <span className="meal-total__unit">kcal</span>
          </div>
          <span className="meal-total__ref">기준 {DAILY_KCAL.toLocaleString('ko-KR')}kcal</span>
        </div>
        <div
          className="meal-bar"
          role="progressbar"
          aria-label="하루 열량"
          aria-valuemin={0}
          aria-valuemax={DAILY_KCAL}
          aria-valuenow={Math.round(totalKcal)}
        >
          <div className="meal-bar__fill" style={{ width: `${percent}%` }} />
        </div>

        {loading && <p className="meal-status">불러오는 중이에요.</p>}

        {loadError && (
          <p className="meal-status meal-status--error" role="alert">
            {loadError}
            <button type="button" className="meal-retry" onClick={retryLoad}>
              다시 불러오기
            </button>
          </p>
        )}

        {!loading && !loadError && (
          <>
            {items.length > 0 && (
              <ul className="meal-list">
                {items.map((item) => {
                  const s = rowSummary(item)
                  return (
                    <li key={item.id}>
                      <button type="button" className="meal-row" onClick={() => navigate(mealRoute(item))}>
                        <span className="meal-row__main">
                          <span className="meal-row__slot">{slotOf(item.eaten_at)}</span>
                          <span className="meal-row__title">{s.title}</span>
                        </span>
                        <span className="meal-row__side">
                          {s.picked && (s.kcal == null ? (
                            <span>정보 없음</span>
                          ) : (
                            <>
                              <span className="meal-row__kcal">{Math.round(s.kcal)}</span>
                              <span>kcal</span>
                            </>
                          ))}
                          <span className="meal-row__chevron" aria-hidden="true">›</span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}

            {emptySlot && (
              <button type="button" className="meal-empty" onClick={openPicker} disabled={uploading}>
                <span className="meal-empty__text">
                  <span className="meal-empty__slot">{emptySlot}</span>
                  <span className="meal-empty__msg">아직 기록하지 않았어요</span>
                </span>
                <span className="meal-empty__add">+ 기록</span>
              </button>
            )}
          </>
        )}

        <Button variant="secondary" fullWidth className="meal-mt-16" onClick={openPicker} loading={uploading}>
          {uploading ? '사진을 올리고 있어요' : '📷 식단 사진 올리기'}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept={IMAGE_TYPES.join(',')}
          onChange={handleFile}
          hidden
        />

        {uploadError && (
          <p className="meal-status meal-status--error" role="alert">
            {uploadError}
          </p>
        )}
      </section>

      <MedicalNotice />
    </div>
  )
}
