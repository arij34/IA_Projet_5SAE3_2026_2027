// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import {
  completeQuizAttempt,
  createSupervisorConnectionTicket,
  getQuizAttempt,
  getQuizAttemptMetrics,
  listChallengeCategories,
  listPublishedChallengeQuizzes,
  recordQuizInteraction,
  submitQuizAnswer,
} from '../api/challenges'
import type { QuizAttemptDetail } from '../types/challenges'
import ChallengeAttemptPage from './ChallengeAttemptPage'
import ChallengesPage from './ChallengesPage'

vi.mock('../api/challenges', () => ({
  completeQuizAttempt: vi.fn(),
  createSupervisorConnectionTicket: vi.fn(),
  generateChallengeQuiz: vi.fn(),
  getQuizAttempt: vi.fn(),
  getQuizAttemptMetrics: vi.fn(),
  listChallengeCategories: vi.fn(),
  listPublishedChallengeQuizzes: vi.fn(),
  recordQuizInteraction: vi.fn(),
  startOrResumeQuizAttempt: vi.fn(),
  submitQuizAnswer: vi.fn(),
}))

vi.mock('../auth/tokenStorage', () => ({
  clearToken: vi.fn(),
  getToken: () => 'test-token',
}))

const attempt: QuizAttemptDetail = {
  id: 12,
  quiz_title: 'Python : maîtriser les fondamentaux',
  category: 'Python',
  difficulty: 'BEGINNER',
  status: 'IN_PROGRESS',
  total_questions: 20,
  answered_count: 0,
  started_at: '2026-10-16T12:00:00Z',
  completed_at: null,
  questions: Array.from({ length: 20 }, (_, index) => ({
    id: 100 + index,
    text: `Question technique ${index + 1}`,
    position: index + 1,
    selected_choice_id: null,
    choices: [
      { id: 1000 + index * 4, text: 'Choix A', position: 1 },
      { id: 1001 + index * 4, text: 'Choix B', position: 2 },
    ],
  })),
}

describe('Challenges landing page', () => {
  beforeEach(() => {
    vi.mocked(listChallengeCategories).mockResolvedValue([
      {
        id: 1,
        name: 'Python',
        slug: 'python',
        description: 'Fondamentaux',
        difficulties: [{ value: 'BEGINNER', label: 'Débutant' }],
      },
    ] as never)
    vi.mocked(listPublishedChallengeQuizzes).mockResolvedValue([
      { id: 5, title: 'Python : maîtriser les fondamentaux', category: 'python', difficulty: 'BEGINNER', question_count: 20 },
    ] as never)
  })

  afterEach(() => cleanup())

  it('offers only published quizzes and no generation action', async () => {
    render(<MemoryRouter><ChallengesPage /></MemoryRouter>)
    expect(await screen.findByRole('button', { name: /Commencer/ })).toBeTruthy()
    expect(screen.getByText(/^20 questions ·/)).toBeTruthy()
    expect(screen.queryByText(/Générer/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /génér/i })).toBeNull()
  })
})

describe('Quiz progress with 20 questions', () => {
  beforeEach(() => {
    vi.mocked(getQuizAttempt).mockResolvedValue(structuredClone(attempt))
    const emptyMetrics = {
      total_questions: 20, submitted_answers: 0, correct_answers: 0,
      incorrect_answers: 0, answer_changes: 0, total_answer_changes: 0, timeout_count: 0,
      unanswered_questions: 20, average_response_seconds: null,
      accuracy_percent: null,
      hesitation: { delayed_first_selection: 0, many_answer_changes: 0, long_response: 0 },
      hesitation_events: 0, time_limit_seconds: 60, question_elapsed_seconds: 0,
    }
    vi.mocked(recordQuizInteraction).mockResolvedValue(emptyMetrics)
    vi.mocked(getQuizAttemptMetrics).mockResolvedValue(emptyMetrics)
    vi.mocked(createSupervisorConnectionTicket).mockRejectedValue(new Error('offline'))
    vi.mocked(submitQuizAnswer).mockResolvedValue({
      id: 81, question_id: 100, selected_choice_id: 1000,
      submitted_at: '2026-10-16T12:01:00Z', answered_count: 1,
      total_questions: 20, already_submitted: false,
    })
    vi.mocked(completeQuizAttempt).mockResolvedValue({} as never)
  })

  afterEach(() => cleanup())

  it('shows "Question 1 sur 20" and a 0 / 20 progress counter', async () => {
    render(
      <MemoryRouter initialEntries={['/challenges/attempts/12']}>
        <Routes>
          <Route path="/challenges/attempts/:attemptId" element={<ChallengeAttemptPage />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByText('Question 1 sur 20')).toBeTruthy()
    expect(screen.getByText('0 / 20')).toBeTruthy()
    const bar = screen.getByRole('progressbar')
    expect(bar.getAttribute('aria-valuemax')).toBe('20')

    fireEvent.click(screen.getByRole('radio', { name: /Choix A/ }))
    fireEvent.click(screen.getByRole('button', { name: /Valider ma réponse/ }))
    await waitFor(() => expect(submitQuizAnswer).toHaveBeenCalledTimes(1))
  })

  it('starts a fresh server-synchronized timer when the next question becomes active', async () => {
    render(
      <MemoryRouter initialEntries={['/challenges/attempts/12']}>
        <Routes>
          <Route path="/challenges/attempts/:attemptId" element={<ChallengeAttemptPage />} />
        </Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Temps restant : 1:00')
    fireEvent.click(screen.getByRole('radio', { name: /Choix A/ }))
    fireEvent.click(screen.getByRole('button', { name: /Valider ma réponse/ }))
    expect(await screen.findByText('Question 2 sur 20')).toBeTruthy()
    await waitFor(() => expect(recordQuizInteraction).toHaveBeenCalledWith(12, 101, 'view', undefined, expect.any(AbortSignal)))
    expect(await screen.findByText('Temps restant : 1:00')).toBeTruthy()
  })
})
