import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Loader2, X } from 'lucide-react'
import { ApiError } from '../../../api/client'
import ScoreBreakdown from '../components/ScoreBreakdown'
import SkillMatchList from '../components/SkillMatchList'
import {
  listMyRecommendations,
  listRecommendedProjects,
  respondToRecommendation,
} from '../services/matchingApi'
import type { Recommendation, RecommendedProject } from '../types'
import '../styles/matching.css'

type PageState = 'loading' | 'ready' | 'error' | 'forbidden'

const PAGE_SIZE = 5

function formatBudget(project: RecommendedProject): string {
  if (project.budget_min && project.budget_max) {
    return `${project.budget_min.toLocaleString('fr-FR')} à ${project.budget_max.toLocaleString(
      'fr-FR',
    )} €`
  }
  return `${Number(project.estimated_amount).toLocaleString('fr-FR')} €`
}

/** Page freelance : projets publiés recommandés et invitations reçues. */
function FreelancerProjectRecommendations() {
  const [page, setPage] = useState(1)
  const [semantic, setSemantic] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeTone, setNoticeTone] = useState<'success' | 'error'>('success')
  const [answered, setAnswered] = useState<Recommendation[]>([])
  const [respondingId, setRespondingId] = useState<number | null>(null)

  const requestKey = `${page}|${semantic}`
  const [outcome, setOutcome] = useState<{
    key: string
    status: PageState
    projects: RecommendedProject[]
    count: number
    recommendations: Recommendation[]
  }>({ key: '', status: 'loading', projects: [], count: 0, recommendations: [] })

  useEffect(() => {
    let mounted = true
    void Promise.all([
      listRecommendedProjects({ page, pageSize: PAGE_SIZE, semantic }),
      listMyRecommendations({ pageSize: 20 }),
    ])
      .then(([feed, invitations]) => {
        if (!mounted) return
        setOutcome({
          key: requestKey,
          status: 'ready',
          projects: feed.results,
          count: feed.count,
          recommendations: invitations.results,
        })
      })
      .catch((error: unknown) => {
        if (!mounted) return
        setOutcome({
          key: requestKey,
          status:
            error instanceof ApiError && error.status === 403
              ? 'forbidden'
              : 'error',
          projects: [],
          count: 0,
          recommendations: [],
        })
      })
    return () => {
      mounted = false
    }
  }, [page, semantic, requestKey])

  const fresh = outcome.key === requestKey
  const pageState: PageState = fresh ? outcome.status : 'loading'
  const projects = fresh ? outcome.projects : []
  const count = fresh ? outcome.count : 0
  const recommendations = (fresh ? outcome.recommendations : []).map(
    (item) => answered.find((updated) => updated.id === item.id) ?? item,
  )

  const handleRespond = async (
    invitation: Recommendation,
    decision: 'accept' | 'decline',
  ) => {
    if (respondingId !== null) return
    setRespondingId(invitation.id)
    setNotice(null)
    try {
      const updated = await respondToRecommendation(invitation.id, decision)
      setAnswered((current) => [...current, updated])
      setNoticeTone('success')
      setNotice(
        decision === 'accept'
          ? `Vous avez accepté l'invitation sur « ${invitation.project_name} ». Le porteur en est informé.`
          : `Vous avez refusé l'invitation sur « ${invitation.project_name} ».`,
      )
    } catch (error: unknown) {
      setNoticeTone('error')
      setNotice(
        error instanceof ApiError && error.status === 409
          ? 'Cette invitation a déjà reçu une réponse.'
          : "Votre réponse n'a pas pu être enregistrée. Réessayez.",
      )
    } finally {
      setRespondingId(null)
    }
  }

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const pending = recommendations.filter((item) => item.status === 'PROPOSED')

  return (
    <div className="container matching-page">
      <div className="matching-header">
        <div>
          <h1>Projets recommandés</h1>
          <p>
            Projets publiés classés selon vos compétences déclarées, votre tarif
            et vos résultats de quiz.
          </p>
        </div>
        <label className="matching-toggle" htmlFor="freelance-semantic-toggle">
          <input
            id="freelance-semantic-toggle"
            type="checkbox"
            checked={semantic}
            onChange={(event) => {
              setPage(1)
              setSemantic(event.target.checked)
            }}
          />
          Analyse sémantique IA
        </label>
      </div>

      <div aria-live="polite">
        {notice ? (
          <p
            className={`matching-notice is-${noticeTone}`}
            role={noticeTone === 'error' ? 'alert' : 'status'}
          >
            {notice}
          </p>
        ) : null}
      </div>

      <section aria-labelledby="matching-invitations">
        <h2 className="matching-subtitle" id="matching-invitations">
          Invitations reçues
        </h2>
        {pending.length === 0 ? (
          <p className="matching-state">
            {pageState === 'ready'
              ? "Vous n'avez aucune invitation en attente. Les porteurs de projet vous inviteront depuis vos recommandations."
              : 'Chargement de vos invitations...'}
          </p>
        ) : (
          <ul className="matching-list">
            {pending.map((invitation) => {
              const busy = respondingId === invitation.id
              return (
                <li className="card" key={invitation.id}>
                  <div className="match-card-head">
                    <div className="match-identity">
                      <h3>{invitation.project_name}</h3>
                      <p>
                        {invitation.speciality
                          ? `Un porteur vous propose la spécialité « ${invitation.speciality} » sur ce projet.`
                          : 'Un porteur de projet vous a invité sur ce projet.'}
                      </p>
                      <div className="match-badges">
                        <span className="match-badge is-warning">
                          Réponse attendue
                        </span>
                        {invitation.score_snapshot !== null ? (
                          <span className="match-badge">
                            Score au moment de l'invitation :{' '}
                            {Math.round(invitation.score_snapshot)}/100
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="matching-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-small"
                        onClick={() => handleRespond(invitation, 'accept')}
                        disabled={respondingId !== null}
                        aria-busy={busy}
                        aria-label={`Accepter l'invitation sur ${invitation.project_name}`}
                      >
                        {busy ? (
                          <Loader2 aria-hidden="true" size={15} />
                        ) : (
                          <Check aria-hidden="true" size={15} />
                        )}
                        {busy ? 'Envoi...' : 'Accepter'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-small"
                        onClick={() => handleRespond(invitation, 'decline')}
                        disabled={respondingId !== null}
                        aria-busy={busy}
                        aria-label={`Refuser l'invitation sur ${invitation.project_name}`}
                      >
                        <X aria-hidden="true" size={15} />
                        Refuser
                      </button>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <h2 className="matching-subtitle">Projets ouverts qui vous correspondent</h2>

      {pageState === 'loading' ? (
        <p className="matching-state" role="status" aria-busy="true">
          Recherche des projets adaptés à votre profil...
        </p>
      ) : null}

      {pageState === 'forbidden' ? (
        <div className="matching-state is-error" role="alert">
          <p>
            Votre profil doit être validé par un administrateur pour accéder aux
            recommandations.
          </p>
          <Link className="btn btn-secondary btn-small" to="/profile">
            Compléter mon profil
          </Link>
        </div>
      ) : null}

      {pageState === 'error' ? (
        <div className="matching-state is-error" role="alert">
          <p>Les projets recommandés n'ont pas pu être chargés.</p>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => setPage(1)}
          >
            Réessayer
          </button>
        </div>
      ) : null}

      {pageState === 'ready' && projects.length === 0 ? (
        <div className="matching-state">
          <p>
            Aucun projet publié et analysé ne correspond encore à votre profil.
            Enrichissez vos compétences déclarées et passez des challenges pour
            améliorer vos scores.
          </p>
          <div className="matching-actions is-centered">
            <Link className="btn btn-primary btn-small" to="/profile">
              Compléter mon profil
            </Link>
            <Link className="btn btn-secondary btn-small" to="/challenges">
              Passer un challenge
            </Link>
            <Link className="btn btn-secondary btn-small" to="/projects/published">
              Voir tous les projets publiés
            </Link>
          </div>
        </div>
      ) : null}

      {pageState === 'ready' && projects.length > 0 ? (
        <>
          <ul className="matching-list">
            {projects.map((project) => (
              <li className="card" key={project.project_id}>
                <div className="match-card-head">
                  <div className="match-identity">
                    <h3>{project.name}</h3>
                    <p>{project.description.slice(0, 220)}</p>
                    <div className="match-badges">
                      <span className="match-badge">
                        Budget : {formatBudget(project)}
                      </span>
                      <span className="match-badge">
                        Échéance : {project.deadline}
                      </span>
                      {project.duree_semaines ? (
                        <span className="match-badge">
                          Durée : {project.duree_semaines} semaines
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="match-score">
                    <strong>{Math.round(project.match.total_score)}</strong>
                    <span>sur 100</span>
                  </div>
                </div>

                <div className="skill-match-group">
                  <h4>Compétences demandées</h4>
                  <div className="match-badges">
                    {project.required_specialities.map((speciality) => (
                      <span className="match-badge" key={speciality.nom}>
                        {speciality.nom} · {speciality.niveau} · {speciality.nb} poste(s)
                      </span>
                    ))}
                  </div>
                </div>

                <ScoreBreakdown
                  subscores={project.match.subscores}
                  weights={project.match.applied_weights}
                />

                <SkillMatchList
                  matched={project.match.subscores.skills?.matched ?? []}
                  missing={project.match.subscores.skills?.missing ?? []}
                />

                <ul className="match-explanations">
                  {project.match.explanations.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          <nav className="matching-pagination" aria-label="Pagination des projets">
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1}
            >
              Page précédente
            </button>
            <span className="breakdown-detail" aria-live="polite">
              Page {page} sur {totalPages} · {count} projet(s)
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              disabled={page >= totalPages}
            >
              Page suivante
            </button>
          </nav>
        </>
      ) : null}
    </div>
  )
}

export default FreelancerProjectRecommendations
