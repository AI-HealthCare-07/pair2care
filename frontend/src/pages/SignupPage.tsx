// frontend/src/pages/SignupPage.tsx
// S-02 회원가입 + S-03 약관 동의 (Figma M01은 한 화면). 가입되면 바로 로그인 상태 → S-06 가입 설문으로

import { useId, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/common/Button'
import Checkbox from '../components/common/Checkbox'
import Chip from '../components/common/Chip'
import Input from '../components/common/Input'
import Select from '../components/common/Select'
import { signup, TERMS_VERSION, type Agreement, type Gender } from '../api/auth'
import { ApiError } from '../api/client'

// 서버 규칙과 같음 (api.md 2-1): 8자 이상, 영문·숫자·특수문자(키보드 기호) 각 1개 이상, 공백·한글 안 됨
const PASSWORD_RULE = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[!-/:-@[-`{-~])[!-~]{8,}$/
const EMAIL_RULE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_HINT = '8자 이상, 영문+숫자+특수문자(!@#$ 등)'

const TERMS: { key: Agreement; label: string }[] = [
  { key: 'TERMS', label: '(필수) 이용약관' },
  { key: 'PRIVACY', label: '(필수) 개인정보 수집·이용' },
  { key: 'SENSITIVE_HEALTH', label: '(필수) 건강정보(민감정보) 처리' },
]

type Field = 'email' | 'password' | 'nickname' | 'gender' | 'birthday' | 'terms'
type Errors = Partial<Record<Field, string>>

const thisYear = new Date().getFullYear()
// 만 14세 미만은 서버가 400 → 목록도 14년 전까지만 (같은 해 생일 전은 서버가 막음)
const YEARS = Array.from({ length: thisYear - 14 - 1920 + 1 }, (_, i) => String(thisYear - 14 - i))
const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1))

export default function SignupPage() {
  const navigate = useNavigate()
  const genderLabelId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [nickname, setNickname] = useState('')
  const [gender, setGender] = useState<Gender | null>(null)
  const [year, setYear] = useState('')
  const [month, setMonth] = useState('')
  const [day, setDay] = useState('')
  const [agreed, setAgreed] = useState<Record<Agreement, boolean>>({ TERMS: false, PRIVACY: false, SENSITIVE_HEALTH: false })
  const [openTerm, setOpenTerm] = useState<Agreement | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [alert, setAlert] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const allAgreed = TERMS.every((t) => agreed[t.key])
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
    if (!allAgreed) next.terms = '필수 약관에 모두 동의해 주세요.'
    return next
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setPasswordTouched(true)
    setAlert(null)
    const found = validate()
    setErrors(found)
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
        consents: TERMS.map((t) => ({ agreement: t.key, version: TERMS_VERSION, is_agreed: true })),
      })
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
    if (err.status === 409) return setErrors({ email: err.message }) // 이미 가입된 이메일
    if (err.status === 400 && err.message.includes('14세')) return setErrors({ birthday: err.message })
    if (err.status === 400) return setErrors({ terms: err.message }) // 약관 동의·버전
    if (err.status === 422) return setAlert('입력값을 확인해 주세요.')
    setAlert('가입하지 못했어요. 잠시 후 다시 시도해 주세요.')
  }

  /** 칸을 고치면 그 칸의 오류 문구는 바로 지움 (다음 제출 때 다시 검사) */
  function clearError(field: Field) {
    if (errors[field]) setErrors({ ...errors, [field]: undefined })
  }

  function toggleAll() {
    clearError('terms')
    const next = !allAgreed
    setAgreed({ TERMS: next, PRIVACY: next, SENSITIVE_HEALTH: next })
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
        <div className="auth__row" role="radiogroup" aria-labelledby={genderLabelId}>
          <Chip mode="radio" selected={gender === 'MALE'} onClick={() => {
              setGender('MALE')
              clearError('gender')
            }}>
            남성
          </Chip>
          <Chip mode="radio" selected={gender === 'FEMALE'} onClick={() => {
              setGender('FEMALE')
              clearError('gender')
            }}>
            여성
          </Chip>
        </div>
        {errors.gender && <p className="auth__hint is-error" role="alert">{errors.gender}</p>}
      </div>

      <fieldset className="auth__fieldset">
        <legend className="auth__legend">생년월일</legend>
        <div className="auth__row auth__birth">
          <Select
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
        <Checkbox strong checked={allAgreed} onChange={toggleAll}>
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
            {/* shortcut: 약관 전문이 아직 없음. 전문이 정해지면 이 자리에 내용(또는 모달)을 넣음 */}
            {openTerm === t.key && <p className="auth__term-body">약관 전문은 준비 중이에요.</p>}
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
