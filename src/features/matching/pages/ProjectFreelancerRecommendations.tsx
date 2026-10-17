import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { ApiError } from '../../../api/client'
import MatchScoreCard from '../components/MatchScoreCard'
import MatchingNav from '../components/MatchingNav'
import ProjectPicker from '../components/ProjectPicker'
import { useProjectName } from '../hooks/useProjectName'
import {
  inviteFreelancer,
  listProjectFreelancers,
  refreshProjectMatching,
} from '../services/matchingApi'
import type { FreelancerMatch } from '../types'
import '../styles/matching.css'

type PageState = 'loading' | 'ready' | 'error' | 'forbidden' | 'no-analysis'

const PAGE_SIZE = 5

/** Page porteur : freelances recommandés pour l'un de ses projets. */
function ProjectFreelancerRecommendations() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const [page, setPage] = useState(1)
  const [semantic, setSemantic] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [invitedIds, setInvitedIds] = useState<number[]>([])
  const [invitingId, setInvitingId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeTone, setNoticeTone] = useState<'info' | 'success' | 'error'>('info')
  const projectName = useProjectName(id)

  const requestKey = `${id}|${page}|${semantic}|${reloadToken}`
  const [outcome, setOutcome] = useState<{
    key: string
    status: PageState
    matches: FreelancerMatch[]
    count: number
  }>({ key: '', status: 'loading', matches: [], count: 0 })

  useEffect(() => {
    if (!Number.isFinite(id) || id <= 0) return
    let mounted = true
    void listProjectFreelancers(id, { page, pageSize: PAGE_SIZE, semantic })
      .then((payload) => {
        if (!mounted) return
        setOutcome({
          key: requestKey,
          status: 'ready',
          matches: payload.results,
          count: payload.count,
        })
      })
      .catch((error: unknown) => {
        if (!mounted) return
        let status: PageState = 'error'
        if (error instanceof ApiError && error.status === 403) status = 'forbidden'
        else if (error instanceof ApiError && error.status === 409)
          status = 'no-analysis'
        setOutcome({ key: requestKey, status, matches: [], count: 0 })
      })
    return () => {
      mounted = false
    }
  }, [id, page, semantic, requestKey])

  const fresh = outcome.key === requestKey
  const pageState: PageState = fresh ? outcome.status : 'loading'
  const matches = fresh ? outcome.matches : []
  const count = fresh ? outcome.count : 0
  const load = useCallback(() => setReloadToken((value) => value + 1), [])

  const announce = (message: string, tone: 'info' | 'success' | 'error') => {
    setNotice(message)
    setNoticeTone(tone)
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    setNotice(null)
    try {
      const result = await refreshProjectMatching(id, semantic)
      if (semantic && result.semantic_unavailable) {
        announce(
          "L'analyse sémantique est indisponible : les scores affichés sont déterministes.",
          'info',
        )
      } else {
        announce(
          `Scores recalculés pour ${result.computed} profil(s).`,
          'success',
        )
      }
      setPage(1)
      load()
    } catch (error: unknown) {
      announce(
        error instanceof ApiError && error.status === 429
          ? 'Trop de recalculs demandés. Réessayez plus tard.'
          : 'Le recalcul a échoué.',
        'error',
      )
    } finally {
      setRefreshing(false)
    }
  }

  const handleInvite = async (match: FreelancerMatch) => {
    if (invitingId !== null) return
    setInvitingId(match.freelancer_id)
    setNotice(null)
    try {
      await inviteFreelancer(id, match.freelancer_id, match.speciality)
      setInvitedIds((current) => [...current, match.freelancer_id])
      announce(`Invitation envoyée à ${match.username}.`, 'success')
    } catch {
      announce(
        `L'invitation à ${match.username} n'a pas pu être envoyée.`,
        'error',
      )
    } finally {
      setInvitingId(null)
    }
  }

  if (!Number.isFinite(id) || id <= 0) {
    return (
      <div className="container matching-page">
        <div className="matching-header">
          <div>
            <h1>Freelances recommandés</h1>
            <p>Choisissez un projet analysé pour afficher ses candidats.</p>
          </div>
        </div>
        <ProjectPicker title="Vos projets analysés" />
      </div>
    )
  }

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  return (
    <div className="container matching-page">
      <MatchingNav current="freelancers" projectId={id} projectName={projectName} />

      <div className="matching-header">
        <div>
          <h1>Freelances recommandés</h1>
          <p>
            Classement calculé à partir des spécialités de votre analyse IA, des
            profils validés, de leur tarif et de leurs résultats de quiz.
          </p>
        </div>
        <div className="matching-actions">
          <label className="matching-toggle" htmlFor="semantic-toggle">
            <input
              id="semantic-toggle"
              type="checkbox"
              checked={semantic}
              onChange={(event) => {
                setPage(1)
                setSemantic(event.target.checked)
              }}
            />
            Analyse sémantique IA
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={handleRefresh}
            disabled={refreshing}
            aria-busy={refreshing}
          >
            <RefreshCw aria-hidden="true" size={15} />
            {refreshing ? 'Recalcul en cours...' : 'Recalculer les scores'}
          </button>
        </div>
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

      {pageState === 'loading' ? (
        <p className="matching-state" role="status" aria-busy="true">
          Calcul des recommandations...
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
            spécialités recherchées.
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
          <p>Les recommandations n'ont pas pu être chargées.</p>
          <button type="button" className="btn btn-secondary btn-small" onClick={load}>
            Réessayer
          </button>
        </div>
      ) : null}

      {pageState === 'ready' && matches.length === 0 ? (
        <div className="matching-state">
          <p>
            Aucun freelance validé ne correspond encore à ce projet. Les profils
            doivent être validés par un administrateur pour apparaître ici.
          </p>
          <div className="matching-actions is-centered">
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              Relancer le calcul
            </button>
            <Link className="btn btn-secondary btn-small" to="/matching/projects">
              Choisir un autre projet
            </Link>
          </div>
        </div>
      ) : null}

      {pageState === 'ready' && matches.length > 0 ? (
        <>
          <ul className="matching-list">
            {matches.map((match) => (
              <MatchScoreCard
                key={match.freelancer_id}
                match={match}
                onInvite={handleInvite}
                inviteDisabled={
                  invitedIds.includes(match.freelancer_id) || invitingId !== null
                }
                inviteBusy={invitingId === match.freelancer_id}
                inviteLabel={
                  invitedIds.includes(match.freelancer_id)
                    ? 'Invitation envoyée'
                    : invitingId === match.freelancer_id
                      ? 'Envoi en cours...'
                      : 'Inviter sur ce projet'
                }
              />
            ))}
          </ul>
          <nav className="matching-pagination" aria-label="Pagination des freelances">
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1}
            >
              Page précédente
            </button>
            <span className="breakdown-detail" aria-live="polite">
              Page {page} sur {totalPages} · {count} profil(s)
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

export default ProjectFreelancerRecommendations
