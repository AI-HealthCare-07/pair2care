// frontend/src/components/meal/MedicalNotice.tsx
// 화면 하단 고정 의료 안내 문구 (C-01). S-21·S-22·S-23에서 같이 씀.
// ⚠️ components/common에 이미 같은 안내 컴포넌트가 있으면 그걸 쓰고 이 파일은 지워 주세요.

interface Props {
  /** 임신 중 안내 등 추가 문구 (api.md 10-9 feedback.notice) */
  extra?: string | null
}

export default function MedicalNotice({ extra }: Props) {
  return (
    <div className="meal-notice" role="note">
      <span className="meal-notice__icon" aria-hidden="true">!</span>
      <p className="meal-notice__text">
        의료 진단이 아닌 참고값이에요. 정확한 판단은 의사·보건소와 상담해 주세요.
        {extra ? <> {extra}</> : null}
      </p>
    </div>
  )
}
