// frontend/src/components/meal/FoodSearch.tsx
// "목록에 없어요 → 직접 검색하기" 패널 (api.md 10-8 GET /foods?q=)
// 1차는 foods 18행 안에서만 고름. 식약처 실시간 검색은 범위 밖(정할 것 19번)

import { useEffect, useState } from 'react'
import { mealsApi } from '../../api/mealsApi'
import { MealApiError, type Food } from '../../api/meals'
import Input from '../common/Input'
import { servingText } from './mealFormat'

interface Props {
  onSelect: (food: Food) => void
  onClose: () => void
}

export default function FoodSearch({ onSelect, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [foods, setFoods] = useState<Food[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 입력이 멈춘 뒤 0.25초에 검색. 처음(빈 입력)에는 바로 전체 목록
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const items = await mealsApi.listFoods(query.trim() || undefined)
        if (!cancelled) {
          setFoods(items)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof MealApiError ? err.message : '음식 목록을 불러오지 못했어요.')
      }
    }, query ? 250 : 0)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  return (
    <div className="meal-search">
      <Input
        label="음식 이름"
        type="search"
        value={query}
        placeholder="예: 국수"
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
      />

      {error && (
        <p className="meal-status meal-status--error" role="alert">
          {error}
        </p>
      )}
      {foods && foods.length === 0 && !error && (
        <p className="meal-status">찾는 음식이 없어요. 다른 이름으로 검색해 보세요.</p>
      )}

      {foods && foods.length > 0 && (
        <ul className="meal-search__list">
          {foods.map((f) => (
            <li key={f.id}>
              <button type="button" className="meal-search__item" onClick={() => onSelect(f)}>
                <span className="meal-search__name">{f.model_label}</span>
                <span className="meal-search__detail">{servingText(f.serving_size, f.serving_unit, f.kcal)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className="meal-retry" onClick={onClose}>
        닫기
      </button>
    </div>
  )
}
