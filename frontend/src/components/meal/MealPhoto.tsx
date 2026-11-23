// frontend/src/components/meal/MealPhoto.tsx
// 올린 사진. 주소가 비었거나 불러오지 못하면 자리 표시(카메라 아이콘)를 보여 줌

import { useState } from 'react'

export default function MealPhoto({ src }: { src: string }) {
  const [broken, setBroken] = useState(false)

  if (!src || broken) {
    return (
      <div className="meal-photo meal-photo--empty">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
          <circle cx="12" cy="13" r="3.5" />
        </svg>
        <span>업로드한 사진</span>
      </div>
    )
  }
  return <img className="meal-photo" src={src} alt="업로드한 사진" onError={() => setBroken(true)} />
}
