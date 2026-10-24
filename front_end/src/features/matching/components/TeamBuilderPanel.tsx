import { CircleAlert, CircleCheck, TriangleAlert, Wallet } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { TeamProposal, UncoveredReason } from '../types'

interface Props {
  team: TeamProposal
  /** Identifiant réel du projet, pour les actions de l'état vide. */
  projectId: number
}

function formatMoney(value: number | null): string {
  return value === null ? 'non estimé' : `${value.toLocaleString('fr-FR')} €`
}

function formatRate(value: number | null): string {
  return value === null ? 'non renseigné' : `${value.toFixed(2)} € / h`
}

const BUDGET_SOURCES: Record<string, string> = {
  budget_recommande: "budget recommandé par l'analyse IA",
  budget_max: "budget haut de l'analyse IA",
  montant_estime_projet: 'montant estimé saisi sur le projet',
  indisponible: 'aucune référence budgétaire disponible',
}

const UNCOVERED_REASONS: Record<UncoveredReason, string> = {
  aucun_candidat_disponible: 'aucun freelance validé disponible',
  aucun_candidat_suffisamment_compatible:
    'aucun candidat n’atteint le seuil de compatibilité',
  candidats_insuffisants_en_nombre: 'pas assez de candidats distincts',
}

/**
 * Affiche la composition d'équipe proposée.
 *
 * Trois informations sont volontairement séparées : les postes attribués, la
 * couverture réelle des compétences et le respect du budget.
 */
function TeamBuilderPanel({ team, projectId }: Props) {
  const staffingLabel = team.fully_staffed
    ? 'Tous les postes attribués'
    : `${team.assigned_positions} poste(s) attribué(s) sur ${team.required_positions}`
  const coverageLabel = team.fully_covered
    ? 'Compétences couvertes'
    : `${team.skill_covered_positions} poste(s) couvert(s) sur ${team.required_positions}`
  const budgetLabel =
    team.estimated_cost === null
      ? 'Coût non calculable sans membre retenu'
      : team.over_budget
        ? 'Budget dépassé'
        : 'Budget respecté'

  return (
    <>
      {team.alerts.length > 0 ? (
        <div className="matching-notice" role="status">
          {team.alerts.map((alert) => (
            <p key={alert} style={{ margin: 0 }}>
              <TriangleAlert aria-hidden="true" size={14} /> {alert}
            </p>
          ))}
        </div>
      ) : null}

      <div className="team-summary">
        <div className={`team-stat${team.fully_staffed ? ' is-ok' : ' is-warning'}`}>
          <strong>
            {team.assigned_positions}/{team.required_positions}
          </strong>
          <span>postes attribués</span>
          <p className="breakdown-detail">{staffingLabel}</p>
        </div>
        <div className={`team-stat${team.fully_covered ? ' is-ok' : ' is-warning'}`}>
          <strong>
            {team.skill_covered_positions}/{team.required_positions}
          </strong>
          <span>postes couverts par les compétences</span>
          <p className="breakdown-detail">{coverageLabel}</p>
        </div>
        <div
          className={`team-stat${
            team.estimated_cost === null
              ? ''
              : team.over_budget
                ? ' is-warning'
                : ' is-ok'
          }`}
        >
          <strong>{formatMoney(team.estimated_cost)}</strong>
          <span>coût estimé{team.estimated_cost_partial ? ' (partiel)' : ''}</span>
          <p className="breakdown-detail">{budgetLabel}</p>
        </div>
        <div className="team-stat">
          <strong>{formatMoney(team.budget_total)}</strong>
          <span>budget de référence</span>
          <p className="breakdown-detail">
            Source : {BUDGET_SOURCES[team.budget_source] ?? team.budget_source}.
          </p>
        </div>
      </div>

      <p className="matching-assumptions">
        <Wallet aria-hidden="true" size={14} /> Coût estimé sur la base de{' '}
        {team.assumptions.duree_semaines ?? '?'} semaine(s),{' '}
        {team.assumptions.heures_par_semaine} heures par semaine et un taux
        d’engagement de {Math.round(team.assumptions.taux_engagement * 100)} %,
        soit {team.assumptions.heures_par_poste ?? '?'} heures par poste. Les
        montants comparés sont des totaux en euros, jamais des tarifs horaires.
        Seuil de compatibilité retenu : {team.assumptions.score_minimal}/100.
      </p>

      {team.uncovered.length > 0 ? (
        <section aria-labelledby="team-uncovered">
          <h3 className="matching-subtitle" id="team-uncovered">
            Postes non pourvus
          </h3>
          <ul className="matching-list">
            {team.uncovered.map((item) => (
              <li className="card" key={item.speciality}>
                <div className="match-identity">
                  <h3>
                    <CircleAlert aria-hidden="true" size={16} /> {item.speciality}
                  </h3>
                  <p>
                    {item.missing} poste(s) manquant(s) sur {item.required} :{' '}
                    {UNCOVERED_REASONS[item.reason] ?? item.reason}.
                  </p>
                </div>
                {item.best_candidate ? (
                  <p className="breakdown-detail">
                    Meilleur profil écarté : {item.best_candidate.username}
                    {item.best_candidate.title
                      ? ` — ${item.best_candidate.title}`
                      : ''}
                    , score {Math.round(item.best_candidate.score)}/100,
                    compétences{' '}
                    {Math.round(item.best_candidate.skill_score ?? 0)}/100.
                    {item.best_candidate.missing_skills.length > 0
                      ? ` Manque : ${item.best_candidate.missing_skills.join(', ')}.`
                      : ''}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {team.members.length > 0 ? (
        <section aria-labelledby="team-members">
          <h3 className="matching-subtitle" id="team-members">
            Membres retenus
          </h3>
          <div className="matching-table-wrapper">
            <table className="matching-table">
              <caption className="breakdown-detail">
                Un membre par poste, trié par spécialité puis par score.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Spécialité</th>
                  <th scope="col">Freelance</th>
                  <th scope="col">Compétences</th>
                  <th scope="col">Niveau attendu</th>
                  <th scope="col">Tarif</th>
                  <th scope="col">Score</th>
                  <th scope="col">Coût estimé</th>
                </tr>
              </thead>
              <tbody>
                {team.members.map((member) => (
                  <tr key={member.freelancer_id}>
                    <td>{member.speciality}</td>
                    <td>
                      {member.username}
                      {member.title ? ` — ${member.title}` : ''}
                    </td>
                    <td>
                      {member.skill_covered ? (
                        <span className="match-badge is-ok">
                          <CircleCheck aria-hidden="true" size={13} /> couvertes
                        </span>
                      ) : (
                        <span className="match-badge is-missing">
                          manque : {member.missing_skills.join(', ') || 'non précisé'}
                        </span>
                      )}
                    </td>
                    <td>{member.required_level ?? '—'}</td>
                    <td>{formatRate(member.hourly_rate)}</td>
                    <td>{Math.round(member.score)}/100</td>
                    <td>{formatMoney(member.estimated_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className="matching-state">
          <p>
            Aucun freelance validé n’atteint le seuil de compatibilité pour les
            spécialités de ce projet. Abaissez le seuil côté serveur, ou
            attendez que des profils adaptés soient validés.
          </p>
          <div className="matching-actions is-centered">
            <Link
              className="btn btn-secondary btn-small"
              to={`/matching/projects/${projectId}/freelancers`}
            >
              Voir tous les candidats et leurs scores
            </Link>
            <Link className="btn btn-secondary btn-small" to="/matching/projects">
              Choisir un autre projet
            </Link>
          </div>
        </div>
      )}
    </>
  )
}

export default TeamBuilderPanel
