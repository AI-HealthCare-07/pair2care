import type { Challenge, NextChallenge } from './challenges'
import { RequestError } from './challenges'

const demoChallenges: Challenge[] = [
  { id: 1, title: '점심 후 10분 걷기', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 2, target: 3 }, checked_today: false, decision_required: false },
  { id: 2, title: '물 6잔 마시기', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 3, target: 7 }, checked_today: false, decision_required: false },
  { id: 3, title: '단 음료 대신 아메리카노', status: 'ACTIVE', my_status: 'JOINED', this_week: { checked: 1, target: 3 }, checked_today: false, decision_required: false },
]

export function listChallenges(): Challenge[] {
  return demoChallenges.map((challenge) => ({ ...challenge }))
}

function findChallenge(id: number): Challenge {
  const challenge = demoChallenges.find((item) => item.id === id)
  if (!challenge) throw new RequestError(404, '챌린지를 찾을 수 없어요.')
  return challenge
}

export function readChallenge(id: number) {
  const challenge = findChallenge(id)
  return {
    id,
    title: challenge.title,
    timesPerWeek: challenge.this_week.target,
    canCheck: !challenge.decision_required,
    checkedToday: challenge.checked_today,
  }
}

export function checkChallenge(id: number) {
  const challenge = findChallenge(id)
  if (!challenge.checked_today) {
    challenge.checked_today = true
    challenge.this_week = { ...challenge.this_week, checked: challenge.this_week.checked + 1 }
  }
  return challenge.this_week
}

export function undoChallengeCheck(id: number) {
  const challenge = findChallenge(id)
  if (challenge.checked_today) {
    challenge.checked_today = false
    challenge.this_week = { ...challenge.this_week, checked: Math.max(0, challenge.this_week.checked - 1) }
  }
}

export function readNextChallenge(): NextChallenge | null {
  const remaining = (item: Challenge) => item.this_week.target - item.this_week.checked
  const [next] = demoChallenges.filter((item) => !item.checked_today && remaining(item) > 0)
    .sort((first, second) => remaining(first) - remaining(second))
  if (!next) return null
  return {
    challenge_id: next.id,
    message: next.id === 3 ? '다음 음료는 무가당으로 골라볼까요?' : `오늘은 ‘${next.title}’을 해볼까요?`,
    source_title: null,
    source_url: null,
  }
}
