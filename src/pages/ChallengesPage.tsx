import { useEffect, useState } from 'react'
import { ArrowRight, BookOpen, Code2, Layers3, Loader2, LockKeyhole, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  generateChallengeQuiz,
  listChallengeCategories,
  listPublishedChallengeQuizzes,
  startOrResumeQuizAttempt,
} from '../api/challenges'
import { clearToken, getToken } from '../auth/tokenStorage'
import type {
  ChallengeCategory,
  ChallengeDifficulty,
  ChallengeQuizSummary,
} from '../types/challenges'
import './ChallengesPage.css'

type PageState = 'loading' | 'unauthenticated' | 'forbidden' | 'error' | 'ready'

const categoryIcons = [Code2, Layers3, BookOpen, Sparkles]
const categoryTones = ['mint', 'coral', 'blue', 'gold']

function ChallengesPage() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<ChallengeCategory[]>([])
  const [quizzes, setQuizzes] = useState<ChallengeQuizSummary[]>([])
  const [selectedDifficulties, setSelectedDifficulties] = useState<Record<number, ChallengeDifficulty>>({})
  const [pageState, setPageState] = useState<PageState>(getToken() ? 'loading' : 'unauthenticated')
  const [retryCount, setRetryCount] = useState(0)
  const [startingQuizId, setStartingQuizId] = useState<number | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const [generatingCategoryId, setGeneratingCategoryId] = useState<number | null>(null)

  useEffect(() => {
    let isMounted = true

    if (!getToken()) {
      return () => { isMounted = false }
    }

    void Promise.all([listChallengeCategories(), listPublishedChallengeQuizzes()])
      .then(([items, publishedQuizzes]) => {
        if (!isMounted) return
        setCategories(items)
        setQuizzes(publishedQuizzes)
        setSelectedDifficulties(Object.fromEntries(
          items.flatMap((category) => {
            const firstDifficulty = category.difficulties[0]?.value
            return firstDifficulty ? [[category.id, firstDifficulty]] : []
          }),
        ))
        setPageState('ready')
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        if (error instanceof ApiError && error.status === 401) {
          setPageState('unauthenticated')
        } else if (error instanceof ApiError && error.status === 403) {
          setPageState('forbidden')
        } else {
          setPageState('error')
        }
      })

    return () => { isMounted = false }
  }, [retryCount])

  const handleStartQuiz = async (quiz: ChallengeQuizSummary) => {
    if (startingQuizId !== null) return
    setStartingQuizId(quiz.id)
    setStartError(null)
    try {
      const attempt = await startOrResumeQuizAttempt(quiz.id)
      navigate(`/challenges/attempts/${attempt.id}`)
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        clearToken()
        navigate('/login', { replace: true })
      } else if (error instanceof ApiError && error.status === 403) {
        navigate('/profile', { replace: true })
      } else {
        setStartError('Impossible de démarrer ce quiz. Veuillez réessayer.')
      }
    } finally {
      setStartingQuizId(null)
    }
  }

  const handleGenerateQuiz = async (category: ChallengeCategory, difficulty: ChallengeDifficulty) => {
    if (generatingCategoryId !== null) return
    setGeneratingCategoryId(category.id)
    setStartError(null)
    try {
      const quiz = await generateChallengeQuiz(category.slug, difficulty)
      setQuizzes((current) => [quiz, ...current])
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        clearToken()
        navigate('/login', { replace: true })
      } else if (error instanceof ApiError && error.status === 403) {
        navigate('/profile', { replace: true })
      } else if (error instanceof ApiError && error.status === 429) {
        setStartError('Limite de générations atteinte. Réessayez plus tard.')
      } else {
        setStartError('La génération du quiz a échoué. Veuillez réessayer.')
      }
    } finally {
      setGeneratingCategoryId(null)
    }
  }

  const renderCatalog = () => {
    if (pageState === 'loading') {
      return <p className="challenge-state" role="status"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement du catalogue…</p>
    }
    if (pageState === 'unauthenticated') {
      return (
        <div className="challenge-state challenge-access-state">
          <LockKeyhole aria-hidden="true" size={24} />
          <div><h2>Connectez-vous pour explorer les challenges</h2><p>Le catalogue est réservé aux membres dont le compte a été validé.</p></div>
          <Link className="btn btn-primary" to="/login">Se connecter <ArrowRight aria-hidden="true" size={16} /></Link>
        </div>
      )
    }
    if (pageState === 'forbidden') {
      return <p className="alert alert-info" role="status">Votre compte doit être validé pour accéder au catalogue des challenges.</p>
    }
    if (pageState === 'error') {
      return (
        <div className="challenge-state challenge-error-state" role="alert">
          <p>Le catalogue est momentanément indisponible.</p>
          <button className="btn btn-secondary" type="button" onClick={() => { setPageState('loading'); setRetryCount((count) => count + 1) }}>Réessayer</button>
        </div>
      )
    }
    if (categories.length === 0) {
      return <p className="challenge-state">Aucune catégorie n’est disponible pour le moment.</p>
    }

    return (
      <div className="challenge-category-grid">
        {startError && <p className="alert alert-error challenge-start-error" role="alert">{startError}</p>}
        {categories.map((category, index) => {
          const Icon = categoryIcons[index % categoryIcons.length]
          const tone = categoryTones[index % categoryTones.length]
          const selectedDifficulty = selectedDifficulties[category.id] ?? category.difficulties[0]?.value
          const availableQuizzes = quizzes.filter(
            (quiz) => quiz.category === category.slug && quiz.difficulty === selectedDifficulty,
          )
          const quiz = availableQuizzes[0]
          const isStarting = quiz !== undefined && startingQuizId === quiz.id
          return (
            <article className={`challenge-category-card tone-${tone}`} key={category.id}>
              <div className="challenge-card-heading">
                <span className="challenge-category-icon"><Icon aria-hidden="true" size={21} /></span>
                <span className="challenge-question-count">
                  {availableQuizzes.length > 0
                    ? `${availableQuizzes.length} quiz disponible${availableQuizzes.length === 1 ? '' : 's'}`
                    : 'Parcours à venir'}
                </span>
              </div>
              <h3>{category.name}</h3>
              <p className="challenge-category-description">{category.description}</p>
              <label className="challenge-difficulty-label" htmlFor={`difficulty-${category.id}`}>Difficulté</label>
              <select
                className="form-input challenge-difficulty-select"
                id={`difficulty-${category.id}`}
                value={selectedDifficulty ?? ''}
                onChange={(event) => setSelectedDifficulties((current) => ({
                  ...current,
                  [category.id]: event.target.value as ChallengeDifficulty,
                }))}
                disabled={category.difficulties.length === 0}
              >
                {category.difficulties.map((difficulty) => (
                  <option key={difficulty.value} value={difficulty.value}>{difficulty.label}</option>
                ))}
              </select>
              <button
                className="btn challenge-start-button"
                type="button"
                disabled={!quiz || startingQuizId !== null}
                aria-describedby={`coming-soon-${category.id}`}
                onClick={() => { if (quiz) void handleStartQuiz(quiz) }}
              >
                {isStarting ? <><Loader2 className="spin" aria-hidden="true" size={16} /> Préparation…</> : quiz ? 'Commencer' : 'Bientôt'}
                {!isStarting && <ArrowRight aria-hidden="true" size={16} />}
              </button>
              <button
                className="btn btn-secondary challenge-start-button"
                type="button"
                disabled={!selectedDifficulty || generatingCategoryId !== null || startingQuizId !== null}
                onClick={() => { if (selectedDifficulty) void handleGenerateQuiz(category, selectedDifficulty) }}
              >
                {generatingCategoryId === category.id
                  ? <><Loader2 className="spin" aria-hidden="true" size={16} /> Génération…</>
                  : <><Sparkles aria-hidden="true" size={16} /> Générer un quiz IA</>}
              </button>
              <small className="challenge-coming-soon" id={`coming-soon-${category.id}`}>
                {quiz ? `${quiz.question_count} questions · Votre progression sera enregistrée.` : 'Aucun quiz publié pour ce niveau.'}
              </small>
            </article>
          )
        })}
      </div>
    )
  }

  return (
    <main className="page-shell challenges-page">
      <section className="challenges-intro" aria-labelledby="challenges-title">
        <div className="challenges-intro-copy">
          <p className="eyebrow">Atelier technique</p>
          <h1 id="challenges-title">Challenges</h1>
          <p>Choisissez un domaine et préparez votre prochain défi technique.</p>
        </div>
        <div className="challenge-intro-mark" aria-hidden="true"><Sparkles size={30} /></div>
      </section>

      <section className="challenge-catalog" aria-labelledby="catalog-title">
        <div className="challenge-section-heading">
          <div><span className="challenge-section-kicker">Votre prochain défi</span><h2 id="catalog-title">Choisissez une catégorie</h2></div>
          {pageState === 'ready' && <span className="challenge-category-total">{categories.length} catégories</span>}
        </div>
        {renderCatalog()}
      </section>

      <p className="challenge-next-step"><span>01</span> Choisissez votre niveau maintenant ; les parcours interactifs arrivent bientôt.</p>
    </main>
  )
}

export default ChallengesPage