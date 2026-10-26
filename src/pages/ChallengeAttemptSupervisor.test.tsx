// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import {
  completeQuizAttempt,
  createSupervisorConnectionTicket,
  getQuizAttempt,
  getQuizAttemptMetrics,
  recordQuizInteraction,
  submitQuizAnswer,
} from '../api/challenges'
import { ApiError } from '../api/client'
import type { QuizAttemptDetail } from '../types/challenges'
import ChallengeAttemptPage from './ChallengeAttemptPage'

vi.mock('../api/challenges', () => ({
  completeQuizAttempt: vi.fn(),
  createSupervisorConnectionTicket: vi.fn(),
  getQuizAttempt: vi.fn(),
  getQuizAttemptMetrics: vi.fn(),
  recordQuizInteraction: vi.fn(),
  submitQuizAnswer: vi.fn(),
}))

class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly url: string
  readonly protocols: string[]
  readyState = MockWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  send = vi.fn()
  close = vi.fn((code = 1000) => {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code } as CloseEvent)
  })

  constructor(url: string, protocols: string[]) {
    this.url = url
    this.protocols = protocols
    MockWebSocket.instances.push(this)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  receive(data: string) {
    this.onmessage?.({ data } as MessageEvent<string>)
  }

  disconnect(code: number) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code } as CloseEvent)
  }
}

const attempt: QuizAttemptDetail = {
  id: 12,
  quiz_title: 'Python basics',
  category: 'Python',
  difficulty: 'BEGINNER',
  status: 'IN_PROGRESS',
  total_questions: 1,
  answered_count: 0,
  started_at: '2026-10-16T12:00:00Z',
  completed_at: null,
  questions: [
    {
      id: 21,
      text: 'Which syntax assigns a value?',
      position: 1,
      selected_choice_id: null,
      choices: [{ id: 32, text: 'value = 1', position: 1 }],
    },
  ],
}

function renderAttemptPage() {
  return render(
    <MemoryRouter initialEntries={['/challenges/attempts/12']}>
      <Routes>
        <Route
          path="/challenges/attempts/:attemptId"
          element={<ChallengeAttemptPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

function supervisorFrame(attemptId = 12) {
  return JSON.stringify({
    type: 'supervisor.event',
    event: {
      id: 41,
      attempt_id: attemptId,
      trigger_type: 'positive_feedback',
      message: 'Continuez ainsi et relisez chaque étape.',
      prompt_version: 'quiz-supervisor-v1',
      generation_status: 'FALLBACK',
      llm_provider: 'mock',
      created_at: '2026-10-16T12:01:00Z',
    },
  })
}

describe('supervisor feedback on a quiz attempt', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.mocked(createSupervisorConnectionTicket).mockResolvedValue({
      ticket: 'single-use-test-ticket',
      expires_at: '2026-10-16T12:02:00Z',
    })
    vi.mocked(getQuizAttempt).mockResolvedValue(attempt)
    vi.mocked(getQuizAttemptMetrics).mockResolvedValue({
      total_questions: 1, submitted_answers: 0, correct_answers: 0,
      incorrect_answers: 0, answer_changes: 0, total_answer_changes: 0, timeout_count: 0,
      unanswered_questions: 1, average_response_seconds: null,
      accuracy_percent: null,
      hesitation: { delayed_first_selection: 0, many_answer_changes: 0, long_response: 0 },
      hesitation_events: 0, time_limit_seconds: 60,
    })
    vi.mocked(recordQuizInteraction).mockResolvedValue({
      total_questions: 1, submitted_answers: 0, correct_answers: 0,
      incorrect_answers: 0, answer_changes: 0, total_answer_changes: 0, timeout_count: 0,
      unanswered_questions: 1, average_response_seconds: null,
      accuracy_percent: null,
      hesitation: { delayed_first_selection: 0, many_answer_changes: 0, long_response: 0 },
      hesitation_events: 0, time_limit_seconds: 60, question_elapsed_seconds: 0,
    })
    vi.mocked(submitQuizAnswer).mockResolvedValue({
      id: 51,
      question_id: 21,
      selected_choice_id: 32,
      submitted_at: '2026-10-16T12:01:00Z',
      answered_count: 1,
      total_questions: 1,
      already_submitted: false,
    })
    vi.mocked(completeQuizAttempt).mockResolvedValue({
      id: 12,
      status: 'COMPLETED',
      correct_answers: 1,
      total_questions: 1,
      score_percent: 100,
      completed_at: '2026-10-16T12:02:00Z',
    })
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('deduplicates and scopes messages while preserving answer submission and completion', async () => {
    renderAttemptPage()

    await screen.findByRole('heading', { name: 'Python basics' })
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))

    expect(createSupervisorConnectionTicket).toHaveBeenCalledWith(12)
    expect(MockWebSocket.instances).toHaveLength(1)
    const socket = MockWebSocket.instances[0]
    expect(socket.protocols).toEqual([
      'freelancy.supervisor.v1',
      'ticket.single-use-test-ticket',
    ])
    expect(socket.url).not.toContain('single-use-test-ticket')
    expect(screen.getByText('Connexion au superviseur…')).toBeTruthy()

    act(() => socket.open())
    expect(screen.getByText(/Superviseur actif/)).toBeTruthy()
    act(() => {
      socket.receive(supervisorFrame())
      socket.receive(supervisorFrame())
      socket.receive(supervisorFrame(99))
    })
    expect(screen.queryByText(/Superviseur actif/)).toBeNull()

    expect(screen.getAllByText('Continuez ainsi et relisez chaque étape.')).toHaveLength(1)
    expect(screen.getByText('Conseil de secours')).toBeTruthy()
    expect(socket.send).toHaveBeenCalledTimes(2)
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'ack', event_id: 41 }),
    )

    fireEvent.click(screen.getByRole('radio', { name: 'value = 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Valider ma réponse' }))
    await screen.findByText('Réponse enregistrée. Elle sera évaluée à la fin du quiz.')
    expect(submitQuizAnswer).toHaveBeenCalledWith(12, 21, 32)

    fireEvent.click(screen.getByRole('button', { name: 'Terminer le quiz' }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(completeQuizAttempt).toHaveBeenCalledWith(12)
    expect(vi.mocked(recordQuizInteraction).mock.calls[0][4]?.aborted).toBe(true)
    expect(vi.mocked(getQuizAttemptMetrics).mock.calls[0][1]?.aborted).toBe(true)
    expect(socket.close).toHaveBeenCalledWith(1000)
  })

  it('reconnects with a fresh ticket after an unexpected close and cleans up', async () => {
    vi.mocked(createSupervisorConnectionTicket)
      .mockResolvedValueOnce({
        ticket: 'first-single-use-ticket',
        expires_at: '2026-10-16T12:02:00Z',
      })
      .mockResolvedValueOnce({
        ticket: 'second-single-use-ticket',
        expires_at: '2026-10-16T12:02:00Z',
      })
    const { unmount } = renderAttemptPage()
    await screen.findByRole('heading', { name: 'Python basics' })
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))
    vi.useFakeTimers()
    const firstSocket = MockWebSocket.instances[0]
    act(() => firstSocket.disconnect(1006))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
      await Promise.resolve()
    })

    expect(createSupervisorConnectionTicket).toHaveBeenCalledTimes(2)
    expect(MockWebSocket.instances).toHaveLength(2)
    const secondSocket = MockWebSocket.instances[1]
    expect(secondSocket.protocols).toContain('ticket.second-single-use-ticket')
    act(() => secondSocket.open())
    unmount()
    expect(secondSocket.close).toHaveBeenCalledWith(1000)
  })

  it('does not retry the ticket after a 500 and still saves answers', async () => {
    vi.mocked(createSupervisorConnectionTicket).mockRejectedValue(
      new ApiError(500, { detail: 'Server error' }),
    )
    const { unmount } = renderAttemptPage()

    expect(
      await screen.findByText(
        'Les conseils du superviseur sont indisponibles. Vous pouvez continuer le quiz.',
      ),
    ).toBeTruthy()
    vi.useFakeTimers()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000)
    })
    expect(createSupervisorConnectionTicket).toHaveBeenCalledTimes(1)
    expect(MockWebSocket.instances).toHaveLength(0)
    vi.useRealTimers()

    fireEvent.click(screen.getByRole('radio', { name: 'value = 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Valider ma réponse' }))
    await screen.findByText('Réponse enregistrée. Elle sera évaluée à la fin du quiz.')
    expect(submitQuizAnswer).toHaveBeenCalledWith(12, 21, 32)
    unmount()
  })

  it('loads persisted metrics when resuming an attempt on an answered question', async () => {
    vi.mocked(getQuizAttempt).mockResolvedValue({
      ...attempt,
      answered_count: 1,
      questions: [{ ...attempt.questions[0], selected_choice_id: 32 }],
    })

    renderAttemptPage()

    await screen.findByText('Réponse enregistrée. Elle sera évaluée à la fin du quiz.')
    await waitFor(() => {
      expect(getQuizAttemptMetrics).toHaveBeenCalledWith(12, expect.any(AbortSignal))
    })
  })

  it('keeps answer submission available when ticket authorization fails', async () => {
    vi.mocked(createSupervisorConnectionTicket).mockRejectedValueOnce(
      new ApiError(403, { detail: 'Forbidden' }),
    )
    renderAttemptPage()

    expect(
      await screen.findByText(
        'Les conseils du superviseur sont indisponibles. Vous pouvez continuer le quiz.',
      ),
    ).toBeTruthy()
    fireEvent.click(screen.getByRole('radio', { name: 'value = 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Valider ma réponse' }))

    await screen.findByText('Réponse enregistrée. Elle sera évaluée à la fin du quiz.')
    expect(submitQuizAnswer).toHaveBeenCalledWith(12, 21, 32)
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('records the active question and selected answer without repeating identical selections', async () => {
    renderAttemptPage()
    await screen.findByText('Temps restant : 1:00')
    expect(recordQuizInteraction).toHaveBeenCalledWith(12, 21, 'view', undefined, expect.any(AbortSignal))
    const answerChoice = screen.getAllByRole('radio', { name: 'value = 1' })[0]
    fireEvent.click(answerChoice)
    fireEvent.click(answerChoice)
    await waitFor(() => expect(recordQuizInteraction).toHaveBeenCalledWith(12, 21, 'select', 32, expect.any(AbortSignal)))
    expect(vi.mocked(recordQuizInteraction).mock.calls.filter((call) => call[2] === 'select')).toHaveLength(1)
  })

  it('records a timer expiration once and never submits an unanswered choice', async () => {
    vi.useFakeTimers()
    vi.mocked(recordQuizInteraction).mockResolvedValue({
      total_questions: 1, submitted_answers: 0, correct_answers: 0,
      incorrect_answers: 0, answer_changes: 0, total_answer_changes: 0, timeout_count: 0,
      unanswered_questions: 1, average_response_seconds: null,
      accuracy_percent: null,
      hesitation: { delayed_first_selection: 0, many_answer_changes: 0, long_response: 0 },
      hesitation_events: 0, time_limit_seconds: 1, question_elapsed_seconds: 0,
    })
    renderAttemptPage()
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
    expect(vi.mocked(recordQuizInteraction).mock.calls.filter((call) => call[2] === 'timeout')).toHaveLength(1)
    expect(submitQuizAnswer).not.toHaveBeenCalled()
  })

  it('shows an unavailable metrics state while keeping answer submission usable', async () => {
    vi.mocked(recordQuizInteraction).mockRejectedValue(new Error('offline'))
    vi.mocked(getQuizAttemptMetrics).mockRejectedValue(new Error('offline'))
    renderAttemptPage()
    expect(await screen.findByText(/Métriques indisponibles pour le moment/)).toBeTruthy()
    fireEvent.click(screen.getByRole('radio', { name: 'value = 1' }))
    fireEvent.click(screen.getByRole('button', { name: /Valider ma réponse/ }))
    expect(await screen.findByText('Réponse enregistrée. Elle sera évaluée à la fin du quiz.')).toBeTruthy()
    expect(submitQuizAnswer).toHaveBeenCalledWith(12, 21, 32)
  })
})
