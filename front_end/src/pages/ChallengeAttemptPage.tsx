import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, CircleAlert, Loader2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { completeQuizAttempt, getQuizAttempt, submitQuizAnswer } from '../api/challenges'
import { clearToken } from '../auth/tokenStorage'
import SupervisorFeedback from '../components/SupervisorFeedback'
import type { QuizAttemptDetail } from '../types/challenges'
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
  const savedChoiceId = question?.selected_choice_id ?? null
  const selectedChoiceId = savedChoiceId ?? pendingChoiceId
  const progress = attempt && attempt.total_questions > 0
    ? Math.round((attempt.answered_count / attempt.total_questions) * 100)
    : 0

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

  const handleComplete = async () => {
    if (!attempt || attempt.answered_count !== attempt.total_questions || isCompleting) return
    setActionErrorMessage(null)
    setIsCompleting(true)
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
        <span className="challenge-play-eyebrow">{attempt.category} · {attempt.difficulty}</span>
        <h1>{attempt.quiz_title}</h1>
        <div className="challenge-progress-label"><span>Progression</span><span>{attempt.answered_count} / {attempt.total_questions}</span></div>
        <div className="challenge-progress-track" role="progressbar" aria-label="Progression du quiz" aria-valuemin={0} aria-valuemax={attempt.total_questions} aria-valuenow={attempt.answered_count}>
          <span style={{ width: `${progress}%` }} />
        </div>
      </section>

      {actionErrorMessage && <p className="alert alert-error" role="alert"><CircleAlert aria-hidden="true" size={17} />{actionErrorMessage}</p>}

      <SupervisorFeedback attemptId={attempt.id} />

      <section className="challenge-question-panel" aria-labelledby={`question-${question.id}`}>
        <div className="challenge-question-count">Question {currentIndex + 1} sur {attempt.total_questions}</div>
        <h2 id={`question-${question.id}`}>{question.text}</h2>
        <fieldset className="challenge-choice-list" disabled={savedChoiceId !== null || isSubmitting}>
          <legend className="sr-only">Sélectionnez une réponse</legend>
          {question.choices.map((choice) => (
            <label className={`challenge-choice${selectedChoiceId === choice.id ? ' is-selected' : ''}${savedChoiceId === choice.id ? ' is-saved' : ''}`} key={choice.id}>
              <input
                type="radio"
                name={`question-${question.id}`}
                value={choice.id}
                checked={selectedChoiceId === choice.id}
                onChange={() => setPendingChoiceId(choice.id)}
              />
              <span>{choice.text}</span>
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
    </main>
  )
}

export default ChallengeAttemptPage