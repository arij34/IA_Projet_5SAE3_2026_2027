import { useState } from 'react'
import { useParams } from 'react-router-dom'
import MatchScoreCard from '../components/MatchScoreCard'
import MatchingNav from '../components/MatchingNav'
import ProjectPicker from '../components/ProjectPicker'
import { useProjectName } from '../hooks/useProjectName'
import { inviteFreelancer, smartMatchProject } from '../services/matchingApi'
import type { FreelancerMatch } from '../types'
import '../styles/matching.css'

/** Page porteur : rechercher puis afficher les meilleurs profils pour un projet. */
function ProjectFreelancerRecommendations() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [invitedIds, setInvitedIds] = useState<number[]>([])
  const [invitingId, setInvitingId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeTone, setNoticeTone] = useState<'info' | 'success' | 'error'>('info')
  const [smartDescription, setSmartDescription] = useState('')
  const [smartBusy, setSmartBusy] = useState(false)
  const [smartResults, setSmartResults] = useState<FreelancerMatch[] | null>(null)
  const [smartCriteria, setSmartCriteria] = useState<{ skills: string[]; budget: number | null; duration_weeks: number | null; level: string | null } | null>(null)
  const projectName = useProjectName(id)

  const announce = (message: string, tone: 'info' | 'success' | 'error') => {
    setNotice(message)
    setNoticeTone(tone)
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
      announce(`L'invitation à ${match.username} n'a pas pu être envoyée.`, 'error')
    } finally {
      setInvitingId(null)
    }
  }

  const handleSmartMatch = async () => {
    setSmartBusy(true)
    setNotice(null)
    setSmartResults(null)
    setSmartCriteria(null)
    try {
      const result = await smartMatchProject(id, smartDescription)
      setSmartResults(result.results.slice(0, 3))
      setSmartCriteria(result.criteria)
      announce(
        result.criteria_available
          ? 'Critères extraits et profils classés.'
          : 'Extraction indisponible : classement existant utilisé.',
        'info',
      )
    } catch {
      announce('Le matching intelligent est indisponible pour le moment.', 'error')
    } finally {
      setSmartBusy(false)
    }
  }

  if (!Number.isFinite(id) || id <= 0) {
    return (
      <div className="container matching-page">
        <div className="matching-header">
          <div>
            <h1>Freelances recommandés</h1>
            <p>Choisissez un projet analysé pour rechercher les profils adaptés.</p>
          </div>
        </div>
        <ProjectPicker title="Vos projets analysés" />
      </div>
    )
  }

  return (
    <div className="container matching-page">
      <MatchingNav current="freelancers" projectId={id} projectName={projectName} />

      <div className="matching-header">
        <div>
          <h1>Freelances recommandés</h1>
          <p>Décrivez votre besoin pour trouver les profils les plus adaptés à votre projet.</p>
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

      <section className="skill-match-group" aria-labelledby="smart-match-title">
        <h2 id="smart-match-title">Assistant de matching IA</h2>
        <label htmlFor="smart-match-description">Décrivez votre besoin</label>
        <textarea
          id="smart-match-description"
          maxLength={3000}
          rows={4}
          value={smartDescription}
          onChange={(event) => setSmartDescription(event.target.value)}
        />
        <button
          type="button"
          className="btn btn-primary btn-small"
          onClick={handleSmartMatch}
          disabled={smartBusy || !smartDescription.trim()}
          aria-busy={smartBusy}
        >
          {smartBusy ? 'Analyse en cours...' : 'Trouver les meilleurs profils'}
        </button>
        {smartCriteria ? (
          <p className="breakdown-detail">
            Critères : {smartCriteria.skills.join(', ') || 'compétences non précisées'} · Budget :{' '}
            {smartCriteria.budget ?? 'non précisé'} · Durée :{' '}
            {smartCriteria.duration_weeks ?? 'non précisée'} sem. · Niveau :{' '}
            {smartCriteria.level ?? 'non précisé'}
          </p>
        ) : null}
        {smartResults?.length === 0 ? (
          <p className="matching-state">Aucun profil ne correspond à cette recherche. Essayez de préciser votre besoin.</p>
        ) : null}
        {smartResults && smartResults.length > 0 ? (
          <ul className="matching-list">
            {smartResults.map((match) => (
              <MatchScoreCard
                key={`smart-${match.freelancer_id}`}
                match={match}
                onInvite={handleInvite}
                inviteDisabled={invitedIds.includes(match.freelancer_id) || invitingId !== null}
                inviteBusy={invitingId === match.freelancer_id}
                inviteLabel={invitedIds.includes(match.freelancer_id) ? 'Invitation envoyée' : 'Inviter sur ce projet'}
              />
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  )
}

export default ProjectFreelancerRecommendations
