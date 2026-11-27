// frontend/src/pages/SignupPage.tsx
// S-02 회원가입 + S-03 약관 동의 (Figma M01은 한 화면). 가입되면 바로 로그인 상태 → S-06 가입 설문으로

import { useId, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/common/Button'
import Checkbox from '../components/common/Checkbox'
import Chip from '../components/common/Chip'
import Input from '../components/common/Input'
import Select from '../components/common/Select'
import { moveRadioFocus } from '../components/common/radioKeys'
import { signup, TERMS_VERSION, type Agreement, type Gender } from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'

// 서버 규칙과 같음 (api.md 2-1): 8자 이상, 영문·숫자·특수문자(키보드 기호) 각 1개 이상, 공백·한글 안 됨
const PASSWORD_RULE = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[!-/:-@[-`{-~])[!-~]{8,}$/
const EMAIL_RULE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_HINT = '8자 이상, 영문+숫자+특수문자(!@#$ 등)'

const TERMS: { key: Agreement; label: string; required: boolean; detail?: string }[] = [
  { key: 'TERMS', label: '(필수) 이용약관', required: true },
  { key: 'PRIVACY', label: '(필수) 개인정보 수집·이용', required: true },
  { key: 'SENSITIVE_HEALTH', label: '(필수) 건강정보(민감정보) 처리', required: true },
  // 기본 해제, 안 해도 가입됨. 마이에서 켜고 끌 수 있음 (2-6, docs/feedback-loop.md)
  {
    key: 'MODEL_IMPROVEMENT',
    label: '(선택) 예측 모델 개선에 내 데이터 활용',
    required: false,
    detail: '동의한 뒤의 설문·검진만 이름 없이 학습에 써요. 마이에서 언제든 끌 수 있어요.',
  },
]
const NONE_AGREED: Record<Agreement, boolean> = { TERMS: false, PRIVACY: false, SENSITIVE_HEALTH: false, MODEL_IMPROVEMENT: false }

type Field = 'email' | 'password' | 'nickname' | 'gender' | 'birthday' | 'terms'
type Errors = Partial<Record<Field, string>>

// 화면 순서. 제출했을 때 오류가 있으면 이 순서로 첫 칸에 포커스 (스크린리더·키보드 사용자가 어디가 틀렸는지 바로 알게)
const FIELD_ORDER: Field[] = ['email', 'password', 'nickname', 'gender', 'birthday', 'terms']
const GENDERS: { value: Gender; label: string }[] = [
  { value: 'MALE', label: '남성' },
  { value: 'FEMALE', label: '여성' },
]

const thisYear = new Date().getFullYear()
// 만 14세 미만은 서버가 400 → 목록도 14년 전까지만 (같은 해 생일 전은 서버가 막음)
const YEARS = Array.from({ length: thisYear - 14 - 1920 + 1 }, (_, i) => String(thisYear - 14 - i))
const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1))

export default function SignupPage() {
  const navigate = useNavigate()
  const { reload } = useAuth()
  const genderLabelId = useId()
  const genderErrorId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [nickname, setNickname] = useState('')
  const [gender, setGender] = useState<Gender | null>(null)
  const [year, setYear] = useState('')
  const [month, setMonth] = useState('')
  const [day, setDay] = useState('')
  const [agreed, setAgreed] = useState<Record<Agreement, boolean>>(NONE_AGREED)
  const [openTerm, setOpenTerm] = useState<Agreement | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [alert, setAlert] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const allAgreed = TERMS.every((t) => agreed[t.key]) // "전체 동의"는 선택까지
  const requiredAgreed = TERMS.every((t) => !t.required || agreed[t.key])
  // 월을 고르기 전엔 31일까지, 고르면 그 달 마지막 날까지 (윤년 포함)
  const daysInMonth = month ? lastDay(year, month) : 31
  const days = Array.from({ length: daysInMonth }, (_, i) => String(i + 1))
  const passwordBad = passwordTouched && password !== '' && !PASSWORD_RULE.test(password)

  function validate(): Errors {
    const next: Errors = {}
    if (!EMAIL_RULE.test(email.trim())) next.email = '이메일 형식을 확인해 주세요.'
    if (!PASSWORD_RULE.test(password)) next.password = PASSWORD_HINT
    const nick = nickname.trim()
    if (nick.length < 2 || nick.length > 20) next.nickname = '닉네임은 2~20자로 입력해 주세요.'
    if (!gender) next.gender = '성별을 골라 주세요.'
    if (!year || !month || !day) next.birthday = '생년월일을 모두 골라 주세요.'
    if (!requiredAgreed) next.terms = '필수 약관에 모두 동의해 주세요.'
    return next
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setPasswordTouched(true)
    setAlert(null)
    const found = validate()
    showErrors(found)
    if (Object.keys(found).length > 0) return

    setLoading(true)
    try {
      const birthday = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
      const result = await signup({
        email: email.trim(),
        password,
        nickname: nickname.trim(),
        gender: gender!,
        birthday,
        consents: TERMS.map((t) => ({ agreement: t.key, version: TERMS_VERSION, is_agreed: agreed[t.key] })),
      })
      await reload() // 가드가 새 로그인 상태를 알게 (안 하면 /login으로 튕김)
      navigate(result.has_health_profile ? '/home' : '/onboarding', { replace: true })
    } catch (err) {
      applyServerError(err)
    } finally {
      setLoading(false)
    }
  }

  /** 서버 오류를 해당 칸 아래로. 어느 칸인지 모르면 버튼 위 안내로 */
  function applyServerError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setAlert('가입하지 못했어요. 잠시 후 다시 시도해 주세요.')
      return
    }
    // 문구 글자가 아니라 code로 칸을 고름 (api.md 1장·2-1)
    if (err.status === 409) return showErrors({ email: err.message }) // 이미 가입된 이메일
    if (err.code === 'SIGNUP_UNDER_14') return showErrors({ birthday: err.message })
    if (err.code === 'SIGNUP_TERMS_REQUIRED') return showErrors({ terms: err.message }) // 약관 동의·버전
    if (err.status === 422) return setAlert('입력값을 확인해 주세요.')
    setAlert('가입하지 못했어요. 잠시 후 다시 시도해 주세요.')
  }

  /** 오류 문구를 띄우고 첫 오류 칸으로 포커스 (그린 뒤에 옮겨야 해서 다음 프레임에) */
  function showErrors(found: Errors) {
    setErrors(found)
    const first = FIELD_ORDER.find((field) => found[field])
    if (!first) return
    requestAnimationFrame(() => document.getElementById(focusTargetId(first))?.focus())
  }

  /** 생년월일은 아직 안 고른 칸부터, 성별은 고른 칩(없으면 첫 칩) */
  function focusTargetId(field: Field): string {
    if (field === 'birthday') return !year ? 'signup-year' : !month ? 'signup-month' : 'signup-day'
    if (field === 'gender') return `signup-gender-${gender ?? GENDERS[0].value}`
    return `signup-${field}`
  }

  function chooseGender(value: Gender) {
    setGender(value)
    clearError('gender')
  }

  /** 성별 칩: 방향키로 옮기면 바로 선택 (설문 보기와 같은 키보드 규칙) */
  function handleGenderKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const next = moveRadioFocus(e)
    if (next !== null) chooseGender(GENDERS[next].value)
  }

  /** 칸을 고치면 그 칸의 오류 문구는 바로 지움 (다음 제출 때 다시 검사) */
  function clearError(field: Field) {
    if (errors[field]) setErrors({ ...errors, [field]: undefined })
  }

  function toggleAll() {
    clearError('terms')
    const next = !allAgreed
    setAgreed({ TERMS: next, PRIVACY: next, SENSITIVE_HEALTH: next, MODEL_IMPROVEMENT: next })
  }

  return (
    <AuthLayout
      title="회원가입"
      greeting={['반가워요! 👋', '같이 건강 습관 만들어 봐요']}
      onSubmit={handleSubmit}
      actions={
        <>
          {alert && (
            <p className="auth__alert" role="alert">
              ⚠️ {alert}
            </p>
          )}
          <Button type="submit" fullWidth loading={loading}>
            {loading ? '가입하고 있어요' : '가입하고 설문 시작하기'}
          </Button>
          <div className="auth__links">
            <span>이미 계정이 있나요?</span>
            <Link to="/login">로그인</Link>
          </div>
        </>
      }
    >
      <Input
        id="signup-email"
        label="이메일"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        placeholder="example@email.com"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value)
          clearError('email')
        }}
        error={errors.email}
      />

      {/* 비밀번호 규칙은 처음부터 보여 주고, 안 맞으면 같은 문구가 빨갛게 바뀜 (S-02) */}
      <div className="auth__group">
        <Input
          id="signup-password"
          label="비밀번호"
          type="password"
          name="new-password"
          autoComplete="new-password"
          placeholder="비밀번호 입력"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            clearError('password')
          }}
          onBlur={() => setPasswordTouched(true)}
          aria-describedby="password-rule"
          aria-invalid={passwordBad || !!errors.password || undefined}
          className={passwordBad ? 'is-invalid' : undefined}
        />
        <p id="password-rule" className={`auth__hint${passwordBad || errors.password ? ' is-error' : ''}`}>
          {PASSWORD_HINT}
        </p>
      </div>

      <Input
        id="signup-nickname"
        label="닉네임"
        name="nickname"
        autoComplete="nickname"
        placeholder="2~20자 · 짝꿍에게 보이는 이름"
        maxLength={20}
        value={nickname}
        onChange={(e) => {
          setNickname(e.target.value)
          clearError('nickname')
        }}
        error={errors.nickname}
      />

      <div className="auth__fieldset">
        <span id={genderLabelId} className="auth__legend">
          성별
        </span>
        <div
          className="auth__row"
          role="radiogroup"
          aria-labelledby={genderLabelId}
          // 오류 표시는 칩(radio)이 아니라 묶음(radiogroup)에. 문구를 이어 둬서 스크린리더가 오류까지 같이 읽음
          aria-invalid={errors.gender ? true : undefined}
          aria-describedby={errors.gender ? genderErrorId : undefined}
          onKeyDown={handleGenderKeyDown}
        >
          {GENDERS.map((option) => (
            <Chip
              key={option.value}
              id={`signup-gender-${option.value}`}
              mode="radio"
              selected={gender === option.value}
              // 탭으로는 고른 칩(없으면 첫 칩) 하나만 들어오고, 그 안에서는 방향키로 옮김
              tabIndex={(gender ?? GENDERS[0].value) === option.value ? 0 : -1}
              onClick={() => chooseGender(option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
        {errors.gender && (
          <p id={genderErrorId} className="auth__hint is-error" role="alert">
            {errors.gender}
          </p>
        )}
      </div>

      <fieldset className="auth__fieldset">
        <legend className="auth__legend">생년월일</legend>
        <div className="auth__row auth__birth">
          <Select
            id="signup-year"
            aria-label="태어난 해"
            placeholder="년"
            value={year}
            onChange={(e) => {
              const nextYear = e.target.value
              setYear(nextYear)
              // 윤년이 바뀌면 2월 마지막 날도 바뀜 → 고른 일이 그 달에 없으면 비움 (2000-02-29 → 2001년)
              if (month && day && Number(day) > lastDay(nextYear, month)) setDay('')
              clearError('birthday')
            }}
            options={YEARS.map((y) => ({ value: y, label: `${y}년` }))}
          />
          <Select
            id="signup-month"
            aria-label="태어난 달"
            placeholder="월"
            value={month}
            onChange={(e) => {
              setMonth(e.target.value)
              setDay('') // 달이 바뀌면 없는 날짜(2월 31일 등)가 남지 않게
              clearError('birthday')
            }}
            options={MONTHS.map((m) => ({ value: m, label: `${m}월` }))}
          />
          <Select
            id="signup-day"
            aria-label="태어난 날"
            placeholder="일"
            value={day}
            onChange={(e) => {
              setDay(e.target.value)
              clearError('birthday')
            }}
            options={days.map((d) => ({ value: d, label: `${d}일` }))}
          />
        </div>
        {errors.birthday && <p className="auth__hint is-error" role="alert">{errors.birthday}</p>}
      </fieldset>

      <div className="auth__terms">
        <Checkbox id="signup-terms" strong checked={allAgreed} onChange={toggleAll}>
          전체 동의
        </Checkbox>
        <hr />
        {TERMS.map((t) => (
          <div key={t.key}>
            <div className="auth__term">
              <Checkbox checked={agreed[t.key]} onChange={() => {
                  setAgreed({ ...agreed, [t.key]: !agreed[t.key] })
                  clearError('terms')
                }}>
                {t.label}
              </Checkbox>
              <button
                type="button"
                className="auth__view"
                aria-expanded={openTerm === t.key}
                onClick={() => setOpenTerm(openTerm === t.key ? null : t.key)}
              >
                보기
              </button>
            </div>
            {/* shortcut: 필수 약관 전문이 아직 없음. 전문이 정해지면 이 자리에 내용(또는 모달)을 넣음 */}
            {openTerm === t.key && <p className="auth__term-body">{t.detail ?? '약관 전문은 준비 중이에요.'}</p>}
          </div>
        ))}
        {errors.terms && <p className="auth__hint is-error" role="alert">{errors.terms}</p>}
      </div>
    </AuthLayout>
  )
}

/** 그 달의 마지막 날. 연도를 아직 안 골랐으면 윤년(2000)으로 보고 2월 29일까지 보여 줌 */
function lastDay(year: string, month: string): number {
  return new Date(Number(year || 2000), Number(month), 0).getDate()
}
