import { useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, CircleX, Loader2, Trophy } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getQuizAttemptResults } from '../api/challenges'
import { clearToken } from '../auth/tokenStorage'
import type { QuizAttemptResult } from '../types/challenges'
import './ChallengePlay.css'

type ResultLoadState = {
  attemptId: number | null
  isLoading: boolean
  result: QuizAttemptResult | null
  errorMessage: string | null
}

function ChallengeResultsPage() {
  const navigate = useNavigate()
  const { attemptId: attemptIdParam } = useParams<{ attemptId: string }>()
  const attemptId = Number(attemptIdParam)
  const [loadState, setLoadState] = useState<ResultLoadState>({
    attemptId: null,
    isLoading: true,
    result: null,
    errorMessage: null,
  })
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!Number.isSafeInteger(attemptId) || attemptId < 1) return
    let isMounted = true
    void getQuizAttemptResults(attemptId)
      .then((data) => {
        if (isMounted) setLoadState({ attemptId, isLoading: false, result: data, errorMessage: null })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        if (error instanceof ApiError && error.status === 401) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (error instanceof ApiError && error.status === 403) {
          navigate('/profile', { replace: true })
        } else if (error instanceof ApiError && error.status === 404) {
          setLoadState({ attemptId, isLoading: false, result: null, errorMessage: 'Ce résultat est introuvable ou ne vous appartient pas.' })
        } else if (error instanceof ApiError && error.status === 409) {
          setLoadState({ attemptId, isLoading: false, result: null, errorMessage: 'Terminez le quiz pour consulter votre résultat.' })
        } else {
          setLoadState({ attemptId, isLoading: false, result: null, errorMessage: 'Impossible de charger le résultat. Vérifiez votre connexion et réessayez.' })
        }
      })
    return () => { isMounted = false }
  }, [attemptId, navigate, retryCount])

  const isLoading = loadState.attemptId !== attemptId || loadState.isLoading
  const result = loadState.attemptId === attemptId ? loadState.result : null
  const errorMessage = loadState.attemptId === attemptId ? loadState.errorMessage : null

  if (!Number.isSafeInteger(attemptId) || attemptId < 1) {
    return <main className="page-shell challenge-play-page"><p className="alert alert-error" role="alert">Identifiant de tentative invalide.</p><Link className="btn btn-secondary" to="/challenges">Retour aux challenges</Link></main>
  }
  if (isLoading) {
    return <main className="page-shell challenge-play-page"><p className="loading-state" role="status"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement du résultat…</p></main>
  }
  if (errorMessage || !result) {
    return <main className="page-shell challenge-play-page"><p className="alert alert-error" role="alert">{errorMessage ?? 'Résultat introuvable.'}</p>{errorMessage?.includes('Terminez') ? <Link className="btn btn-primary" to={`/challenges/attempts/${attemptId}`}>Reprendre le quiz</Link> : <button className="btn btn-secondary" type="button" onClick={() => { setLoadState({ attemptId: null, isLoading: true, result: null, errorMessage: null }); setRetryCount((count) => count + 1) }}>Réessayer</button>}</main>
  }

  return (
    <main className="page-shell challenge-play-page">
      <Link className="challenge-back-link" to="/challenges"><ArrowLeft aria-hidden="true" size={16} /> Tous les challenges</Link>
      <section className="challenge-result-summary">
        <span className="challenge-result-icon"><Trophy aria-hidden="true" size={25} /></span>
        <p className="challenge-play-eyebrow">Résultat du challenge</p>
        <h1>{result.quiz_title}</h1>
        <strong className="challenge-score">{result.score_percent}%</strong>
        <p>{result.correct_answers} bonne{result.correct_answers === 1 ? '' : 's'} réponse{result.correct_answers === 1 ? '' : 's'} sur {result.total_questions}</p>
      </section>

      <section className="challenge-results-list" aria-labelledby="answer-review-title">
        <h2 id="answer-review-title">Correction détaillée</h2>
        {result.answers.map((answer, index) => (
          <article className={`challenge-result-answer${answer.is_correct ? ' answer-correct' : ' answer-incorrect'}`} key={answer.question_id}>
            <div className="challenge-result-answer-heading">
              {answer.is_correct ? <CheckCircle2 aria-hidden="true" size={20} /> : <CircleX aria-hidden="true" size={20} />}
              <span>Question {index + 1}</span>
              <strong>{answer.is_correct ? 'Correcte' : 'À revoir'}</strong>
            </div>
            <h3>{answer.question_text}</h3>
            <p><span>Votre réponse :</span> {answer.selected_choice_text}</p>
            {!answer.is_correct && <p><span>Bonne réponse :</span> {answer.correct_choice_text}</p>}
            <p className="challenge-explanation">{answer.explanation}</p>
          </article>
        ))}
      </section>
      <Link className="btn btn-primary challenge-back-to-catalog" to="/challenges">Choisir un autre challenge</Link>
    </main>
  )
}

export default ChallengeResultsPage