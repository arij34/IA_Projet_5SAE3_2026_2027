import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, CircleAlert, Loader2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { completeQuizAttempt, getQuizAttempt, getQuizAttemptMetrics, recordQuizInteraction, submitQuizAnswer } from '../api/challenges'
import { clearToken } from '../auth/tokenStorage'
import SupervisorFeedback from '../components/SupervisorFeedback'
import type { QuizAttemptDetail, QuizAttemptMetrics } from '../types/challenges'
import './ChallengePlay.css'

type AttemptLoadState = {
  attemptId: number | null
  isLoading: boolean
  attempt: QuizAttemptDetail | null
  errorMessage: string | null
}

function ChallengeAttemptPage() {
  const navigate = useNavigate()
  const { attemptId: attemptIdParam } = useParams<{ attemptId: string }>()
  const attemptId = Number(attemptIdParam)
  const [loadState, setLoadState] = useState<AttemptLoadState>({
    attemptId: null,
    isLoading: true,
    attempt: null,
    errorMessage: null,
  })
  const [currentIndex, setCurrentIndex] = useState(0)
  const [pendingChoiceId, setPendingChoiceId] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCompleting, setIsCompleting] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<QuizAttemptMetrics | null>(null)
  const [metricsUnavailable, setMetricsUnavailable] = useState(false)
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null)
  const [timerUnavailable, setTimerUnavailable] = useState(false)
  const [timerQuestionId, setTimerQuestionId] = useState<number | null>(null)
  const [activity, setActivity] = useState<string[]>([])
  const interactionQueue = useRef<Promise<QuizAttemptMetrics | null>>(Promise.resolve(null))
  const requestController = useRef(new AbortController())

  const sendInteraction = useCallback((targetAttemptId: number, questionId: number, event: 'view' | 'select' | 'timeout', choiceId?: number) => {
    const request = interactionQueue.current
      .then(() => requestController.current.signal.aborted
        ? null
        : recordQuizInteraction(targetAttemptId, questionId, event, choiceId, requestController.current.signal))
      .catch(() => null)
    interactionQueue.current = request
    return request
  }, [])

  useEffect(() => {
    if (!Number.isSafeInteger(attemptId) || attemptId < 1) return
    let isMounted = true
    void getQuizAttempt(attemptId)
      .then((data) => {
        if (isMounted) setLoadState({ attemptId, isLoading: false, attempt: data, errorMessage: null })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        if (error instanceof ApiError && error.status === 401) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (error instanceof ApiError && error.status === 403) {
          navigate('/profile', { replace: true })
        } else if (error instanceof ApiError && error.status === 404) {
          setLoadState({ attemptId, isLoading: false, attempt: null, errorMessage: 'Cette tentative est introuvable ou ne vous appartient pas.' })
        } else {
          setLoadState({ attemptId, isLoading: false, attempt: null, errorMessage: 'Impossible de charger le quiz. Vérifiez votre connexion et réessayez.' })
        }
      })
    return () => { isMounted = false }
  }, [attemptId, navigate, retryCount])

  const isLoading = loadState.attemptId !== attemptId || loadState.isLoading
  const attempt = loadState.attemptId === attemptId ? loadState.attempt : null
  const loadErrorMessage = loadState.attemptId === attemptId ? loadState.errorMessage : null
  const question = attempt?.questions[currentIndex]
  const metricsAttemptId = attempt?.id
  const metricsAttemptStatus = attempt?.status
  const savedChoiceId = question?.selected_choice_id ?? null
  const selectedChoiceId = savedChoiceId ?? pendingChoiceId
  const displayedSecondsRemaining = timerQuestionId === question?.id && savedChoiceId === null
    && !isSubmitting
    ? secondsRemaining
    : null
  const displayedTimerUnavailable = timerQuestionId === question?.id && timerUnavailable && savedChoiceId === null
  const timerProgressPercent = displayedSecondsRemaining !== null && metrics
    ? Math.max(0, Math.min(100, displayedSecondsRemaining / metrics.time_limit_seconds * 100))
    : null
  const progress = attempt && attempt.total_questions > 0
    ? Math.round((attempt.answered_count / attempt.total_questions) * 100)
    : 0

  useEffect(() => {
    if (metricsAttemptId === undefined || metricsAttemptStatus !== 'IN_PROGRESS') return
    const controller = new AbortController()
    void getQuizAttemptMetrics(metricsAttemptId, controller.signal)
      .then((data) => {
        setMetrics(data)
        setMetricsUnavailable(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) setMetricsUnavailable(true)
      })
    return () => controller.abort()
  }, [metricsAttemptId, metricsAttemptStatus])

  useEffect(() => {
    if (!attempt || !question || savedChoiceId !== null || attempt.status !== 'IN_PROGRESS' || isSubmitting) return
    let active = true
    let intervalId: number | undefined
    let timeoutSent = false
    let deadline = 0
    void sendInteraction(attempt.id, question.id, 'view')
      .then((data) => {
        if (!active || !data) {
          if (active) {
            setTimerQuestionId(question.id)
            setTimerUnavailable(true)
            setMetricsUnavailable(true)
          }
          return
        }
        setMetrics(data)
        setMetricsUnavailable(false)
        setActivity((items) => [...items, `Question ${currentIndex + 1} affichée`].slice(-4))
        setTimerQuestionId(question.id)
        setTimerUnavailable(false)
        const limit = data.time_limit_seconds
        deadline = Date.now() + Math.max(0, limit - (data.question_elapsed_seconds ?? 0)) * 1000
        const tick = () => {
          if (!active) return
          const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
          setTimerQuestionId(question.id)
          setSecondsRemaining(remaining)
          if (remaining === 0 && !timeoutSent) {
            timeoutSent = true
            setActivity((items) => [...items, `Temps écoulé · question ${currentIndex + 1}`].slice(-4))
            void sendInteraction(attempt.id, question.id, 'timeout').then((result) => {
              if (result) {
                setMetrics(result)
                setMetricsUnavailable(false)
              } else {
                setMetricsUnavailable(true)
              }
            })
          }
        }
        tick()
        intervalId = window.setInterval(tick, 500)
      })
      .catch(() => {
        if (active) {
          setTimerQuestionId(question.id)
          setTimerUnavailable(true)
          setMetricsUnavailable(true)
        }
      })
    return () => {
      active = false
      if (intervalId !== undefined) window.clearInterval(intervalId)
    }
  }, [attempt, currentIndex, isSubmitting, question, savedChoiceId, sendInteraction])

  const handleSubmitAnswer = async () => {
    if (!attempt || !question || selectedChoiceId === null || savedChoiceId !== null || isSubmitting) return
    setActionErrorMessage(null)
    setIsSubmitting(true)
    try {
      const receipt = await submitQuizAnswer(attempt.id, question.id, selectedChoiceId)
      setLoadState((current) => current.attemptId === attempt.id && current.attempt
        ? {
            ...current,
            attempt: {
              ...current.attempt,
              answered_count: receipt.answered_count,
              questions: current.attempt.questions.map((item) => item.id === question.id
                ? { ...item, selected_choice_id: receipt.selected_choice_id }
                : item),
            },
          }
        : current)
      setPendingChoiceId(null)
      setActivity((items) => [...items, `Réponse enregistrée · question ${currentIndex + 1}`].slice(-4))
      void getQuizAttemptMetrics(attempt.id, requestController.current.signal)
        .then((data) => { setMetrics(data); setMetricsUnavailable(false) })
        .catch(() => { setMetricsUnavailable(true) })
      if (currentIndex < attempt.questions.length - 1) setCurrentIndex((index) => index + 1)
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        clearToken()
        navigate('/login', { replace: true })
      } else if (error instanceof ApiError && error.status === 403) {
        navigate('/profile', { replace: true })
      } else if (error instanceof ApiError && error.status === 409) {
        setActionErrorMessage('La tentative a changé. Rechargez son état avant de continuer.')
      } else {
        setActionErrorMessage('Votre réponse n’a pas pu être enregistrée. Vous pouvez réessayer.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleChoiceChange = (choiceId: number) => {
    if (selectedChoiceId === choiceId || !attempt || !question) return
    setPendingChoiceId(choiceId)
    setActivity((items) => [...items, `Réponse modifiée · question ${currentIndex + 1}`].slice(-4))
    void sendInteraction(attempt.id, question.id, 'select', choiceId)
      .then((data) => {
        if (data) {
          setMetrics(data)
          setMetricsUnavailable(false)
        } else {
          setMetricsUnavailable(true)
        }
      })
  }

  const handleComplete = async () => {
    if (!attempt || attempt.answered_count !== attempt.total_questions || isCompleting) return
    setActionErrorMessage(null)
    setIsCompleting(true)
    requestController.current.abort()
    try {
      await completeQuizAttempt(attempt.id)
      navigate(`/challenges/attempts/${attempt.id}/results`)
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        clearToken()
        navigate('/login', { replace: true })
      } else if (error instanceof ApiError && error.status === 403) {
        navigate('/profile', { replace: true })
      } else if (error instanceof ApiError && error.status === 409) {
        setActionErrorMessage('Toutes les réponses doivent être enregistrées avant de terminer.')
      } else {
        setActionErrorMessage('Le quiz n’a pas pu être terminé. Réessayez.')
      }
    } finally {
      setIsCompleting(false)
    }
  }

  if (!Number.isSafeInteger(attemptId) || attemptId < 1) {
    return <main className="page-shell challenge-play-page"><p className="alert alert-error" role="alert">Identifiant de tentative invalide.</p><Link className="btn btn-secondary" to="/challenges">Retour aux challenges</Link></main>
  }
  if (isLoading) {
    return <main className="page-shell challenge-play-page"><p className="loading-state" role="status"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement de votre quiz…</p></main>
  }
  if (loadErrorMessage && !attempt) {
    return <main className="page-shell challenge-play-page"><p className="alert alert-error" role="alert">{loadErrorMessage}</p><button className="btn btn-secondary" type="button" onClick={() => { setLoadState({ attemptId: null, isLoading: true, attempt: null, errorMessage: null }); setRetryCount((count) => count + 1) }}>Réessayer</button></main>
  }
  if (!attempt) return null
  if (attempt.status === 'COMPLETED') {
    return <main className="page-shell challenge-play-page"><section className="challenge-panel"><h1>Quiz terminé</h1><p>Votre tentative est terminée. Consultez votre résultat.</p><Link className="btn btn-primary" to={`/challenges/attempts/${attempt.id}/results`}>Voir mes résultats <ArrowRight aria-hidden="true" size={17} /></Link></section></main>
  }
  if (!question) {
    return <main className="page-shell challenge-play-page"><p className="alert alert-error" role="alert">Ce quiz ne contient aucune question.</p><Link className="btn btn-secondary" to="/challenges">Retour aux challenges</Link></main>
  }

  return (
    <main className="page-shell challenge-play-page">
      <Link className="challenge-back-link" to="/challenges"><ArrowLeft aria-hidden="true" size={16} /> Tous les challenges</Link>
      <section className="challenge-play-header">
        <div className="challenge-play-meta">
          <span className="challenge-play-eyebrow">{attempt.category}</span>
          <span className="challenge-difficulty-badge">{attempt.difficulty}</span>
        </div>
        <h1>{attempt.quiz_title}</h1>
        <div className="challenge-progress-label"><span>Progression</span><span>{attempt.answered_count} / {attempt.total_questions}</span></div>
        <div className="challenge-progress-track" role="progressbar" aria-label="Progression du quiz" aria-valuemin={0} aria-valuemax={attempt.total_questions} aria-valuenow={attempt.answered_count}>
          <span style={{ width: `${progress}%` }} />
        </div>
      </section>

      {actionErrorMessage && <p className="alert alert-error" role="alert"><CircleAlert aria-hidden="true" size={17} />{actionErrorMessage}</p>}

      <div className="challenge-play-layout">
      <section className="challenge-question-panel" aria-labelledby={`question-${question.id}`}>
        <div className="challenge-question-heading">
          <div className="challenge-question-count">Question {currentIndex + 1} sur {attempt.total_questions}</div>
          <div className={`challenge-timer${displayedSecondsRemaining === 0 ? ' is-expired' : ''}`} role="timer" aria-live="off">
            <span>{isSubmitting ? 'Enregistrement…' : displayedSecondsRemaining === 0 ? 'Temps écoulé · question sans réponse' : displayedSecondsRemaining !== null ? `Temps restant : ${Math.floor(displayedSecondsRemaining / 60)}:${String(displayedSecondsRemaining % 60).padStart(2, '0')}` : displayedTimerUnavailable ? 'Minuteur indisponible' : savedChoiceId !== null ? 'Réponse enregistrée' : 'Synchronisation du minuteur…'}</span>
            {timerProgressPercent !== null && <div className="challenge-timer-track" role="progressbar" aria-label="Temps restant pour cette question" aria-valuemin={0} aria-valuemax={metrics?.time_limit_seconds ?? 60} aria-valuenow={displayedSecondsRemaining ?? 0}><span style={{ width: `${timerProgressPercent}%` }} /></div>}
          </div>
        </div>
        <h2 id={`question-${question.id}`}>{question.text}</h2>
        <fieldset className="challenge-choice-list" disabled={savedChoiceId !== null || isSubmitting}>
          <legend className="sr-only">Sélectionnez une réponse</legend>
          {question.choices.map((choice, choiceIndex) => (
            <label className={`challenge-choice${selectedChoiceId === choice.id ? ' is-selected' : ''}${savedChoiceId === choice.id ? ' is-saved' : ''}`} key={choice.id}>
              <input
                type="radio"
                name={`question-${question.id}`}
                value={choice.id}
                checked={selectedChoiceId === choice.id}
                onChange={() => handleChoiceChange(choice.id)}
              />
              <span className="challenge-choice-marker" aria-hidden="true">{String.fromCharCode(65 + choiceIndex)}</span>
              <span className="challenge-choice-text">{choice.text}</span>
              {savedChoiceId === choice.id && <Check aria-hidden="true" size={18} />}
            </label>
          ))}
        </fieldset>
        {savedChoiceId !== null && <p className="challenge-saved-note" role="status">Réponse enregistrée. Elle sera évaluée à la fin du quiz.</p>}
        <div className="challenge-question-actions">
          <button className="btn btn-secondary" type="button" disabled={currentIndex === 0 || isSubmitting} onClick={() => { setPendingChoiceId(null); setCurrentIndex((index) => index - 1) }}>Précédente</button>
          {savedChoiceId === null ? (
            <button className="btn btn-primary" type="button" disabled={selectedChoiceId === null || isSubmitting} onClick={() => void handleSubmitAnswer()}>
              {isSubmitting ? <><Loader2 className="spin" aria-hidden="true" size={17} /> Enregistrement…</> : <>Valider ma réponse <ArrowRight aria-hidden="true" size={16} /></>}
            </button>
          ) : currentIndex < attempt.total_questions - 1 ? (
            <button className="btn btn-primary" type="button" onClick={() => { setPendingChoiceId(null); setCurrentIndex((index) => index + 1) }}>Suivante <ArrowRight aria-hidden="true" size={16} /></button>
          ) : attempt.answered_count === attempt.total_questions ? (
            <button className="btn btn-primary" type="button" disabled={isCompleting} onClick={() => void handleComplete()}>
              {isCompleting ? <><Loader2 className="spin" aria-hidden="true" size={17} /> Calcul du résultat…</> : <>Terminer le quiz <ArrowRight aria-hidden="true" size={16} /></>}
            </button>
          ) : null}
        </div>
        {attempt.answered_count === attempt.total_questions && currentIndex < attempt.total_questions - 1 && (
          <button className="btn btn-secondary challenge-complete-early" type="button" disabled={isCompleting} onClick={() => void handleComplete()}>
            Terminer le quiz
          </button>
        )}
      </section>
      <SupervisorFeedback attemptId={attempt.id} metrics={metrics} metricsUnavailable={metricsUnavailable} secondsRemaining={displayedSecondsRemaining} activity={activity} />
      </div>
    </main>
  )
}

export default ChallengeAttemptPage
