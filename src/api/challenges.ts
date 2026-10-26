import { apiFetch } from './client'
import type {
  ChallengeCategory,
  ChallengeDifficulty,
  ChallengeQuizSummary,
  QuizAttemptCompletion,
  QuizAttemptDetail,
  QuizAttemptResult,
  SupervisorConnectionTicket,
  SubmittedAnswerReceipt,
  QuizAttemptMetrics,
} from '../types/challenges'

export function listChallengeCategories(): Promise<ChallengeCategory[]> {
  return apiFetch<ChallengeCategory[]>('/api/challenges/categories/')
}

export function listPublishedChallengeQuizzes(
  category?: string,
  difficulty?: ChallengeDifficulty,
): Promise<ChallengeQuizSummary[]> {
  const query = new URLSearchParams()
  if (category) query.set('category', category)
  if (difficulty) query.set('difficulty', difficulty)
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return apiFetch<ChallengeQuizSummary[]>(`/api/challenges/quizzes/${suffix}`)
}

export function generateChallengeQuiz(
  category: string,
  difficulty: ChallengeDifficulty,
): Promise<ChallengeQuizSummary> {
  return apiFetch<ChallengeQuizSummary>('/api/challenges/quizzes/generate/', {
    method: 'POST',
    body: { category, difficulty },
  })
}

export function startOrResumeQuizAttempt(quizId: number): Promise<QuizAttemptDetail> {
  return apiFetch<QuizAttemptDetail>('/api/challenges/attempts/', {
    method: 'POST',
    body: { quiz_id: quizId },
  })
}

export function getQuizAttempt(attemptId: number): Promise<QuizAttemptDetail> {
  return apiFetch<QuizAttemptDetail>(`/api/challenges/attempts/${attemptId}/`)
}

export function createSupervisorConnectionTicket(
  attemptId: number,
): Promise<SupervisorConnectionTicket> {
  return apiFetch<SupervisorConnectionTicket>(
    `/api/challenges/attempts/${attemptId}/supervisor-ticket/`,
    { method: 'POST', body: {} },
  )
}

export function submitQuizAnswer(
  attemptId: number,
  questionId: number,
  choiceId: number,
): Promise<SubmittedAnswerReceipt> {
  return apiFetch<SubmittedAnswerReceipt>(`/api/challenges/attempts/${attemptId}/answers/`, {
    method: 'POST',
    body: { question_id: questionId, choice_id: choiceId },
  })
}

export function recordQuizInteraction(
  attemptId: number,
  questionId: number,
  event: 'view' | 'select' | 'timeout',
  choiceId?: number,
  signal?: AbortSignal,
): Promise<QuizAttemptMetrics> {
  return apiFetch<QuizAttemptMetrics>(`/api/challenges/attempts/${attemptId}/interactions/`, {
    method: 'POST',
    body: { question_id: questionId, event, ...(choiceId === undefined ? {} : { choice_id: choiceId }) },
    signal,
  })
}

export function getQuizAttemptMetrics(attemptId: number, signal?: AbortSignal): Promise<QuizAttemptMetrics> {
  return apiFetch<QuizAttemptMetrics>(`/api/challenges/attempts/${attemptId}/metrics/`, { signal })
}

export function completeQuizAttempt(attemptId: number): Promise<QuizAttemptCompletion> {
  return apiFetch<QuizAttemptCompletion>(`/api/challenges/attempts/${attemptId}/complete/`, {
    method: 'POST',
  })
}

export function getQuizAttemptResults(attemptId: number): Promise<QuizAttemptResult> {
  return apiFetch<QuizAttemptResult>(`/api/challenges/attempts/${attemptId}/results/`)
}
