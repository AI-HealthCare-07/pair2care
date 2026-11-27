// frontend/src/pages/SurveyPage.tsx
// S-06 가입 설문 (Figma M02) · REQ-PROF-001, PRED-004 · api.md 3-1(저장)·3-6(문항 정의)
// 한 화면에 한 문항, 진행률(남은 문항 기준 %), 이전·다음. 건너뛰기로 사람마다 문항 수가 다름.
// 흐름: 문항 정의(상수) → 보일 문항 계산 → 답 → 마지막에서 3-1 저장 → 결과 화면으로 이동

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { healthProfilesApi } from '../api/healthProfilesApi'
import { ApiError } from '../api/client'
import { surveyErrorAction } from '../api/healthProfiles'
import Button from '../components/common/Button'
import TopBar from '../components/common/TopBar'
import NumberAnswer from '../components/survey/NumberAnswer'
import OptionList from '../components/survey/OptionList'
import SurveyProgress from '../components/survey/SurveyProgress'
import { SURVEY_DEFINITION_ONBOARDING } from '../survey/definition'
import { firstQuestion, nextQuestion, previousQuestion, progressPercent } from '../survey/navigation'
import { buildSurveyRequest, validateAnswers } from '../survey/payload'
import type { AnswerValue, Gender, SurveyAnswers, SurveyDefinition } from '../survey/types'
import { useGender } from '../survey/useGender'
import { pruneHiddenAnswers, questionText } from '../survey/visibleQuestions'
import '../components/survey/survey.css'

// 저장 뒤 S-09 예측 결과로 (경로는 팀장님 11/25 확정). S-09는 들어올 때 5-2를 다시 부르므로 응답을 넘기지 않음.
// replace: 뒤로 가기로 이미 저장한 설문에 돌아가지 않게 (다시 저장하면 409 ONBOARDING_ALREADY_DONE)
const AFTER_SURVEY_PATH = '/prediction'

interface ServerError {
  message: string
  field: string | null
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="survey-screen">
      <TopBar title="건강 설문" />
      <div className="survey-body">{children}</div>
    </div>
  )
}

export default function SurveyPage() {
  const { gender, error } = useGender()
  if (error) {
    return (
      <Shell>
        <p className="survey-error" role="alert">
          {error}
        </p>
      </Shell>
    )
  }
  if (!gender) {
    return (
      <Shell>
        <p className="survey-help">불러오는 중이에요.</p>
      </Shell>
    )
  }
  return <SurveyFlow key={gender} gender={gender} />
}

function SurveyFlow({ gender }: { gender: Gender }) {
  const navigate = useNavigate()
  const { reload } = useAuth()
  const headingRef = useRef<HTMLHeadingElement>(null)

  const [def, setDef] = useState<SurveyDefinition>(SURVEY_DEFINITION_ONBOARDING)
  const [answers, setAnswers] = useState<SurveyAnswers>({})
  const [currentField, setCurrentField] = useState(
    () => firstQuestion(SURVEY_DEFINITION_ONBOARDING, {}, gender)?.field ?? '',
  )
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [serverError, setServerError] = useState<ServerError | null>(null)

  // 문항이 바뀌면 제목으로 포커스를 옮겨 스크린리더가 새 질문을 읽게 함
  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true })
  }, [currentField])

  const question = def.questions.find((q) => q.field === currentField)
  if (!question) return null

  const previous = previousQuestion(def, answers, currentField, gender)
  const next = nextQuestion(def, answers, currentField, gender)
  const percent = progressPercent(def, answers, currentField, gender)
  const fieldError = validateAnswers(def, answers, gender).find((e) => e.field === currentField)
  const typed = answers[currentField] !== undefined && answers[currentField] !== null
  const title = questionText(question, gender)

  function setAnswer(field: string, value: AnswerValue | undefined) {
    setServerError(null)
    setNotice(null)
    // 앞 문항을 바꿔서 뒤 문항이 숨겨지면 그 답은 지움 (3-1이 건너뛸 문항에 값이 오면 400)
    setAnswers((prev) => pruneHiddenAnswers(def, { ...prev, [field]: value }, gender))
  }

  function goPrevious() {
    if (!previous) return
    setServerError(null)
    setCurrentField(previous.field)
  }

  async function handleNext() {
    if (fieldError || submitting) return
    if (next) {
      setServerError(null)
      setCurrentField(next.field)
      return
    }
    await submit(def, answers)
  }

  async function submit(currentDef: SurveyDefinition, currentAnswers: SurveyAnswers) {
    // 서버는 오류를 하나만 돌려주므로, 먼저 전부 검사해 빠진 문항으로 이동
    const errors = validateAnswers(currentDef, currentAnswers, gender)
    if (errors.length > 0) {
      setCurrentField(errors[0].field)
      return
    }
    setSubmitting(true)
    setServerError(null)
    try {
      await healthProfilesApi.postHealthProfile(buildSurveyRequest(currentDef, currentAnswers, gender))
      await reload() // has_health_profile이 true로 바뀌어야 가드가 다시 설문으로 안 보냄
      navigate(AFTER_SURVEY_PATH, { replace: true })
    } catch (err) {
      await handleSubmitError(err)
    } finally {
      setSubmitting(false)
    }
  }

  // api.md 3-1 에러 목록의 "프론트 처리"
  async function handleSubmitError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setServerError({ message: '설문을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.', field: null })
      return
    }
    switch (surveyErrorAction(err)) {
      case 'RELOAD_DEFINITION': {
        // 설문 버전이 바뀜: 3-6을 다시 받아 화면을 새로 그림 (같은 field의 입력값은 유지)
        try {
          const fresh = await healthProfilesApi.getSurveyDefinition('ONBOARDING')
          const kept = pruneHiddenAnswers(fresh, answers, gender)
          setDef(fresh)
          setAnswers(kept)
          setNotice('설문 문항이 바뀌어 다시 불러왔어요. 확인하고 다시 눌러 주세요.')
          const missing = validateAnswers(fresh, kept, gender)[0]
          const stay = fresh.questions.some((q) => q.field === currentField)
          const fallback = firstQuestion(fresh, kept, gender)?.field ?? currentField
          setCurrentField(missing?.field ?? (stay ? currentField : fallback))
        } catch {
          setServerError({ message: '설문 문항을 다시 불러오지 못했어요. 잠시 후 다시 시도해 주세요.', field: null })
        }
        return
      }
      case 'GO_HOME':
        await reload() // 이미 설문함(409) → 내 정보를 다시 받아야 홈에서 안 튕김
        navigate('/home')
        return
      case 'FOCUS_FIELD':
        // field가 이 화면의 문항이면 그 문항으로 이동, 모르는 값이면 문구만 보여 줌
        if (err.field && def.questions.some((q) => q.field === err.field)) setCurrentField(err.field)
        setServerError({ message: err.message, field: err.field })
        return
      case 'RECHECK_INPUT':
        setServerError({ message: '입력값을 확인해 주세요.', field: null })
        return
      default:
        setServerError({ message: err.message, field: null })
    }
  }

  return (
    <div className="survey-screen">
      <TopBar title="건강 설문" onBack={previous ? goPrevious : undefined} />
      <div className="survey-body">
        {notice && (
          <p className="survey-notice" role="status">
            {notice}
          </p>
        )}
        <SurveyProgress percent={percent} />

        <h2 className="survey-title" id="survey-question" ref={headingRef} tabIndex={-1}>
          {title}
        </h2>
        {question.help && <p className="survey-help">{question.help}</p>}

        {question.type === 'NUMBER' ? (
          <NumberAnswer
            key={question.field}
            question={question}
            labelText={title}
            value={answers[question.field]}
            onChange={(v) => setAnswer(question.field, v)}
            error={typed ? fieldError?.message : undefined}
          />
        ) : (
          <OptionList
            labelledBy="survey-question"
            options={question.options ?? []}
            value={answers[question.field]}
            onChange={(v) => setAnswer(question.field, v)}
          />
        )}

        {serverError && (
          <p className="survey-error" role="alert">
            {serverError.message}
          </p>
        )}

        <div className="survey-actions">
          <Button fullWidth onClick={handleNext} disabled={!!fieldError} loading={submitting}>
            {next ? '다음' : '완료'}
          </Button>
          {previous && (
            <Button variant="ghost" fullWidth onClick={goPrevious} disabled={submitting}>
              이전
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
