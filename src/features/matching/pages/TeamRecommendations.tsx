import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../../api/client'
import MatchingNav from '../components/MatchingNav'
import ProjectPicker from '../components/ProjectPicker'
import TeamBuilderPanel from '../components/TeamBuilderPanel'
import { useProjectName } from '../hooks/useProjectName'
import { getProjectTeam } from '../services/matchingApi'
import type { TeamProposal } from '../types'
import '../styles/matching.css'

type PageState = 'loading' | 'ready' | 'error' | 'forbidden' | 'no-analysis'

/** Page porteur : composition automatique d'équipe pour un projet. */
function TeamRecommendations() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const projectName = useProjectName(id)
  const requestKey = String(id)
  const [outcome, setOutcome] = useState<{
    key: string
    status: PageState
    team: TeamProposal | null
  }>({ key: '', status: 'loading', team: null })

  useEffect(() => {
    if (!Number.isFinite(id) || id <= 0) return
    let mounted = true
    void getProjectTeam(id)
      .then((payload) => {
        if (mounted) {
          setOutcome({ key: requestKey, status: 'ready', team: payload })
        }
      })
      .catch((error: unknown) => {
        if (!mounted) return
        let status: PageState = 'error'
        if (error instanceof ApiError && error.status === 403) status = 'forbidden'
        else if (error instanceof ApiError && error.status === 409)
          status = 'no-analysis'
        setOutcome({ key: requestKey, status, team: null })
      })
    return () => {
      mounted = false
    }
  }, [id, requestKey])

  const pageState: PageState =
    outcome.key === requestKey ? outcome.status : 'loading'
  const team = outcome.key === requestKey ? outcome.team : null

  if (!Number.isFinite(id) || id <= 0) {
    return (
      <div className="container matching-page">
        <div className="matching-header">
          <div>
            <h1>Composition d'équipe</h1>
            <p>Choisissez un projet analysé pour composer son équipe.</p>
          </div>
        </div>
        <ProjectPicker title="Vos projets analysés" />
      </div>
    )
  }

  return (
    <div className="container matching-page">
      <MatchingNav current="team" projectId={id} projectName={projectName} />

      <div className="matching-header">
        <div>
          <h1>Composition d'équipe</h1>
          <p>
            Sélection déterministe couvrant chaque spécialité de l'analyse, sans
            jamais affecter deux fois le même freelance.
          </p>
        </div>
      </div>

      {pageState === 'loading' ? (
        <p className="matching-state" role="status" aria-busy="true">
          Composition de l'équipe en cours...
        </p>
      ) : null}

      {pageState === 'forbidden' ? (
        <div className="matching-state is-error" role="alert">
          <p>Ce projet n'est pas accessible avec votre compte.</p>
          <Link className="btn btn-secondary btn-small" to="/matching/projects">
            Revenir à mes projets
          </Link>
        </div>
      ) : null}

      {pageState === 'no-analysis' ? (
        <div className="matching-state">
          <p>
            Ce projet doit d'abord être analysé par l'IA pour connaître les
            spécialités à pourvoir.
          </p>
          <div className="matching-actions is-centered">
            <Link className="btn btn-primary btn-small" to="/gestion-projets">
              Lancer l'analyse du projet
            </Link>
            <Link className="btn btn-secondary btn-small" to="/matching/projects">
              Choisir un autre projet
            </Link>
          </div>
        </div>
      ) : null}

      {pageState === 'error' ? (
        <div className="matching-state is-error" role="alert">
          <p>La composition d'équipe n'a pas pu être calculée.</p>
          <Link
            className="btn btn-secondary btn-small"
            to={`/matching/projects/${id}/freelancers`}
          >
            Voir les freelances recommandés
          </Link>
        </div>
      ) : null}

      {pageState === 'ready' && team ? (
        <TeamBuilderPanel team={team} projectId={id} />
      ) : null}
    </div>
  )
}

export default TeamRecommendations
