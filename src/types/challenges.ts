export type ChallengeDifficulty = 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED'

export interface ChallengeDifficultyOption {
  value: ChallengeDifficulty
  label: string
}

export interface ChallengeCategory {
  id: number
  slug: string
  name: string
  description: string
  difficulties: ChallengeDifficultyOption[]
}

export interface ChallengeQuizSummary {
  id: number
  title: string
  category: string
  difficulty: ChallengeDifficulty
  question_count: number
}

export type QuizAttemptStatus = 'IN_PROGRESS' | 'COMPLETED'

export interface QuizAnswerChoice {
  id: number
  text: string
  position: number
}

export interface QuizAttemptQuestion {
  id: number
  text: string
  position: number
  choices: QuizAnswerChoice[]
  selected_choice_id: number | null
}

export interface QuizAttemptDetail {
  id: number
  quiz_title: string
  category: string
  difficulty: ChallengeDifficulty
  status: QuizAttemptStatus
  total_questions: number
  answered_count: number
  started_at: string
  completed_at: string | null
  questions: QuizAttemptQuestion[]
}

export interface SubmittedAnswerReceipt {
  id: number
  question_id: number
  selected_choice_id: number
  submitted_at: string
  answered_count: number
  total_questions: number
  already_submitted: boolean
}

export interface QuizAttemptCompletion {
  id: number
  status: 'COMPLETED'
  correct_answers: number
  total_questions: number
  score_percent: number
  completed_at: string
}

export interface QuizAttemptResultAnswer {
  question_id: number
  question_text: string
  selected_choice_id: number
  selected_choice_text: string
  is_correct: boolean
  correct_choice_text: string
  explanation: string
}

export interface QuizAttemptResult {
  id: number
  quiz_title: string
  correct_answers: number
  total_questions: number
  score_percent: number
  completed_at: string
  answers: QuizAttemptResultAnswer[]
}

export type SupervisorTriggerType =
  | 'repeated_errors'
  | 'positive_feedback'
  | 'slow_progress'
  | 'repeated_answer_changes'
  | 'long_response'
  | 'multiple_timeouts'

export interface QuizAttemptMetrics {
  total_questions: number
  submitted_answers: number
  correct_answers: number
  incorrect_answers: number
  answer_changes: number
  total_answer_changes: number
  timeout_count: number
  unanswered_questions: number
  average_response_seconds: number | null
  accuracy_percent: number | null
  hesitation: {
    delayed_first_selection: number
    many_answer_changes: number
    long_response: number
  }
  hesitation_events: number
  time_limit_seconds: number
  question_elapsed_seconds?: number
}

export type SupervisorGenerationStatus = 'GENERATED' | 'FALLBACK'

export interface SupervisorMessage {
  id: number
  attempt_id: number
  trigger_type: SupervisorTriggerType
  message: string
  prompt_version: string
  generation_status: SupervisorGenerationStatus
  llm_provider: string
  created_at: string
}

export type SupervisorConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'unavailable'

export interface SupervisorConnectionTicket {
  ticket: string
  expires_at: string
}
