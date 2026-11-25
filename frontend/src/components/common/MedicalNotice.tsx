// frontend/src/components/common/MedicalNotice.tsx
// 의료 안내 문구 (C-01). 식단(S-21·S-22·S-23)과 예측 결과(S-09)가 같이 씀.
// (components/meal/MedicalNotice.tsx에서 옮김, 문구·모양 그대로)

import './common.css'

interface Props {
  /** 임신 중 안내 등 추가 문구 (예: api.md 10-9 feedback.notice) */
  extra?: string | null
}

export default function MedicalNotice({ extra }: Props) {
  return (
    <div className="ui-notice" role="note">
      <span className="ui-notice__icon" aria-hidden="true">!</span>
      <p className="ui-notice__text">
        의료 진단이 아닌 참고값이에요. 정확한 판단은 의사·보건소와 상담해 주세요.
        {extra ? <> {extra}</> : null}
      </p>
    </div>
  )
}
