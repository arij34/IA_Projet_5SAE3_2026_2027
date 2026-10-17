import { BadgeCheck, Sparkles, TriangleAlert } from 'lucide-react'
import type { FreelancerMatch } from '../types'
import ScoreBreakdown from './ScoreBreakdown'
import SkillMatchList from './SkillMatchList'

interface Props {
  match: FreelancerMatch
  onInvite?: (match: FreelancerMatch) => void
  inviteLabel?: string
  inviteDisabled?: boolean
  inviteBusy?: boolean
}

function formatRate(rate: number | null): string {
  return rate === null ? 'tarif non renseigné' : `${rate.toFixed(2)} € / h`
}

/** Carte d'un freelance recommandé, avec son score explicable. */
function MatchScoreCard({
  match,
  onInvite,
  inviteLabel,
  inviteDisabled,
  inviteBusy,
}: Props) {
  const skills = match.subscores.skills
  const budget = match.subscores.budget
  const quiz = match.subscores.quiz

  return (
    <li className="card">
      <div className="match-card-head">
        <div className="match-identity">
          <h3>{match.username}</h3>
          <p>{match.title || 'Profil sans titre renseigné'}</p>
          <div className="match-badges">
            <span className="match-badge">{formatRate(match.hourly_rate)}</span>
            {match.speciality ? (
              <span className="match-badge">Spécialité : {match.speciality}</span>
            ) : null}
            {match.required_level ? (
              <span className="match-badge">Niveau attendu : {match.required_level}</span>
            ) : null}
            {budget?.available && (budget.score ?? 0) < 50 ? (
              <span className="match-badge is-warning">
                <TriangleAlert aria-hidden="true" size={13} /> Tarif au-dessus du budget
              </span>
            ) : null}
            {match.mode === 'HYBRID' ? (
              <span className="match-badge is-ok">
                <Sparkles aria-hidden="true" size={13} /> Analyse IA incluse
              </span>
            ) : (
              <span className="match-badge">Score déterministe</span>
            )}
          </div>
        </div>
        <div className="match-score">
          <strong>{Math.round(match.total_score)}</strong>
          <span>sur 100</span>
        </div>
      </div>

      <ScoreBreakdown subscores={match.subscores} weights={match.applied_weights} />

      <SkillMatchList
        matched={skills?.matched ?? []}
        missing={skills?.missing ?? []}
        declared={match.skills}
      />

      {quiz?.available && quiz.categories && quiz.categories.length > 0 ? (
        <div className="skill-match-group">
          <h4>Résultats de quiz pris en compte</h4>
          <div className="match-badges">
            {quiz.categories.map((category) => (
              <span className="match-badge" key={category.category}>
                {category.name} : {Math.round(category.average)} % ({category.attempts})
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {match.semantic_available && match.semantic_justification ? (
        <div className="skill-match-group">
          <h4>Analyse sémantique</h4>
          <p className="breakdown-detail">{match.semantic_justification}</p>
        </div>
      ) : null}

      <ul className="match-explanations">
        {match.explanations.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <div className="match-footer">
        <span className="breakdown-detail">
          Score déterministe {Math.round(match.deterministic_score)}/100
          {match.semantic_score !== null
            ? ` · score sémantique ${Math.round(match.semantic_score)}/100`
            : ''}
        </span>
        {onInvite ? (
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={() => onInvite(match)}
            disabled={inviteDisabled}
            aria-busy={inviteBusy}
            aria-label={`${inviteLabel ?? 'Inviter'} : ${match.username}`}
          >
            <BadgeCheck aria-hidden="true" size={15} />
            {inviteLabel ?? 'Inviter'}
          </button>
        ) : null}
      </div>
    </li>
  )
}

export default MatchScoreCard
