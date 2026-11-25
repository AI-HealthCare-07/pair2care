// frontend/src/components/survey/SurveyProgress.tsx
// "60% · 남은 질문 기준" + 진행 막대 (Figma M02). 비율은 survey/navigation.ts의 progressPercent.

import './survey.css'

export default function SurveyProgress({ percent }: { percent: number }) {
  return (
    <div className="survey-progress">
      <p className="survey-progress__label">{percent}% · 남은 질문 기준</p>
      <div
        className="survey-progress__bar"
        role="progressbar"
        aria-label="설문 진행률"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div className="survey-progress__fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}
