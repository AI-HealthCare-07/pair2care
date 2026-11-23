// frontend/src/components/meal/CandidateCard.tsx
// 후보 한 줄 (라디오처럼 하나만 선택). 오른쪽에 '1인분 515mL · 499kcal'

interface Props {
  label: string
  detail: string
  selected: boolean
  onSelect: () => void
  tag?: string
}

export default function CandidateCard({ label, detail, selected, onSelect, tag }: Props) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={`${label}${tag ? `, ${tag}` : ''}, ${detail}`}
      className={`meal-candidate${selected ? ' is-selected' : ''}`}
      onClick={onSelect}
    >
      <span className="meal-candidate__name">
        {label}
        {tag && <span className="meal-candidate__tag">{tag}</span>}
      </span>
      <span className="meal-candidate__detail">{detail}</span>
    </button>
  )
}
