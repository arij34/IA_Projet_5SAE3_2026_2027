import type { Subscore, SubscoreKey } from '../types'

const LABELS: Record<SubscoreKey, string> = {
  skills: 'Compétences',
  budget: 'Budget',
  level: 'Niveau',
  quiz: 'Quiz',
}

const ORDER: SubscoreKey[] = ['skills', 'budget', 'level', 'quiz']

interface Props {
  subscores: Partial<Record<SubscoreKey, Subscore>>
  weights: Partial<Record<SubscoreKey, number>>
}

/** Affiche les quatre sous-scores, y compris ceux qui ont été neutralisés. */
function ScoreBreakdown({ subscores, weights }: Props) {
  return (
    <div className="breakdown-list">
      {ORDER.map((key) => {
        const subscore = subscores[key]
        if (!subscore) return null
        const weight = weights[key]
        const skipped = !subscore.available || subscore.score === null
        return (
          <div className="breakdown-row" key={key}>
            <div className="breakdown-row-head">
              <span>
                {LABELS[key]}
                {weight !== undefined && !skipped
                  ? ` · poids ${Math.round(weight * 100)} %`
                  : ''}
              </span>
              <span>{skipped ? 'non évalué' : `${Math.round(subscore.score ?? 0)}/100`}</span>
            </div>
            <div
              className={`breakdown-meter${skipped ? ' is-skipped' : ''}`}
              role="img"
              aria-label={`${LABELS[key]} : ${
                skipped ? 'critère non évalué' : `${Math.round(subscore.score ?? 0)} sur 100`
              }`}
            >
              <span style={{ width: `${skipped ? 100 : Math.round(subscore.score ?? 0)}%` }} />
            </div>
            {subscore.detail ? (
              <p className="breakdown-detail">{subscore.detail}</p>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export default ScoreBreakdown
