// frontend/src/components/meal/PortionChips.tsx
// 0.5 / 1 / 1.5인분 선택. 공통 Chip을 라디오처럼 사용

import type { Portion } from '../../api/meals'
import Chip from '../common/Chip'
import { PORTIONS, portionLabel } from './mealFormat'

interface Props {
  value: number
  onChange: (p: Portion) => void
}

export default function PortionChips({ value, onChange }: Props) {
  return (
    <div className="meal-chips" role="radiogroup" aria-label="먹은 양">
      {PORTIONS.map((p) => (
        <Chip key={p} mode="radio" selected={value === p} onClick={() => onChange(p)}>
          {portionLabel(p)}
        </Chip>
      ))}
    </div>
  )
}
