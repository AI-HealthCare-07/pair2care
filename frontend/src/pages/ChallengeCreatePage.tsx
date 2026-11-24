import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { dateInSeoul, requireSuccess } from '../api/recommendations'
import Button from '../components/common/Button'
import TopBar from '../components/common/TopBar'
import '../components/recommendation/recommendation.css'

const isDemo = import.meta.env.VITE_USE_MOCK === 'true'
type Partner = { user_id: number; nickname: string }

export default function ChallengeCreatePage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState(isDemo ? '점심 후 10분 걷기' : '')
  const [times, setTimes] = useState(2)
  const [duration, setDuration] = useState(7)
  const [partners, setPartners] = useState<Partner[]>(isDemo ? [{ user_id: 1, nickname: '예시 짝꿍' }] : [])
  const [recipient, setRecipient] = useState(isDemo ? '1' : '')
  const [loading, setLoading] = useState(!isDemo)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const submitting = useRef(false)

  useEffect(() => {
    if (isDemo) return
    const controller = new AbortController()
    async function load() {
      try {
        const response = await apiFetch('/pairs?status=ACCEPTED', { signal: controller.signal })
        if (response.status === 404) throw new Error('짝꿍 초대 기능을 준비하고 있어요.')
        await requireSuccess(response, '짝꿍 목록을 불러오지 못했어요.')
        const data: { items: { partner: Partner }[] } = await response.json()
        if (!controller.signal.aborted) setPartners(data.items.map(({ partner }) => partner))
      } catch (problem) {
        if (!controller.signal.aborted) setError(problem instanceof Error ? problem.message : '짝꿍 목록을 불러오지 못했어요.')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  async function send(event: FormEvent) {
    event.preventDefault()
    if (submitting.current || !recipient || !title.trim() || sent) return
    submitting.current = true
    setSending(true)
    setError('')
    try {
      if (!isDemo) {
        const response = await apiFetch('/challenges', {
          method: 'POST',
          body: JSON.stringify({
            challenge_template_id: null,
            title: title.trim(),
            times_per_week: times,
            starts_on: dateInSeoul(),
            ends_on: dateInSeoul(duration - 1),
            mode: 'PAIR',
            invite_user_ids: [Number(recipient)],
          }),
        })
        if (response.status === 404) throw new Error('챌린지 초대 기능을 준비하고 있어요.')
        await requireSuccess(response, '초대를 보내지 못했어요.')
        if (response.status !== 201) throw new Error('초대 결과를 확인하지 못했어요.')
      }
      setSent(true)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : '초대를 보내지 못했어요.')
    } finally {
      submitting.current = false
      setSending(false)
    }
  }

  return (
    <main className="challenge-page">
      <TopBar title="챌린지 만들기" onBack={() => navigate('/home')} />
      <section className="daily-page">
        <div className="daily-card">
          {sent ? (
            <>
              <h2 role="status">{isDemo ? '초대 화면 체험을 마쳤어요' : '짝꿍에게 초대를 보냈어요'}</h2>
              {isDemo && <p>실제 초대는 전송되지 않았어요.</p>}
              <Link to="/home">홈으로 돌아가기</Link>
            </>
          ) : (
            <form className="challenge-form" onSubmit={send}>
              {isDemo && <p className="daily-context">체험 모드 · 실제 초대를 보내지 않아요</p>}
              <label>챌린지 이름 <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={100} /></label>
              <label>기간 <select value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={7}>7일</option><option value={14}>14일</option><option value={28}>28일</option></select></label>
              <label>주간 목표 <select value={times} onChange={(event) => setTimes(Number(event.target.value))}>{Array.from({ length: 7 }, (_, i) => i + 1).map((number) => <option key={number} value={number}>각자 {number}회</option>)}</select></label>
              <label>짝꿍 <select required value={recipient} disabled={loading || !partners.length} onChange={(event) => setRecipient(event.target.value)}><option value="">{loading ? '목록 불러오는 중' : '짝꿍 선택'}</option>{partners.map((partner) => <option key={partner.user_id} value={partner.user_id}>{partner.nickname}</option>)}</select></label>
              {!loading && !partners.length && !error && <p>초대할 수 있는 짝꿍이 없어요. <Link to="/pairs">짝꿍 보기</Link></p>}
              <p className="daily-context">짝꿍에게 챌린지 이름, 기간, 목표가 공유돼요.</p>
              {error && <p role="alert">{error}</p>}
              <Button variant="accent" type="submit" fullWidth disabled={!recipient || !title.trim()} loading={sending}>초대 보내기</Button>
            </form>
          )}
        </div>
      </section>
    </main>
  )
}
