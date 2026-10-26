import { Bot, Loader2, TriangleAlert, TrendingUp, WifiOff } from 'lucide-react'
import { useSupervisorChannel } from '../hooks/useSupervisorChannel'
import type { QuizAttemptMetrics, SupervisorConnectionStatus } from '../types/challenges'

function connectionMessage(status: SupervisorConnectionStatus): string | null {
  if (status === 'connecting') return 'Connexion au superviseur…'
  if (status === 'reconnecting') return 'Connexion interrompue. Nouvelle tentative…'
  if (status === 'unavailable') {
    return 'Les conseils du superviseur sont indisponibles. Vous pouvez continuer le quiz.'
  }
  if (status === 'connected') {
    return 'Superviseur actif. Des conseils peuvent apparaître selon votre progression.'
  }
  return null
}

function SupervisorFeedback({ attemptId, metrics, metricsUnavailable, secondsRemaining, activity }: {
  attemptId: number
  metrics: QuizAttemptMetrics | null
  metricsUnavailable: boolean
  secondsRemaining: number | null
  activity: string[]
}) {
  const { messages, status } = useSupervisorChannel(attemptId)
  const statusMessage = messages.length === 0 || status !== 'connected'
    ? connectionMessage(status)
    : null
  const isPending = status === 'connecting' || status === 'reconnecting'

  return (
    <aside className={`supervisor-feedback is-${status}`} aria-label="Panneau du superviseur IA">
      <header className="supervisor-header">
        <span className="supervisor-icon" aria-hidden="true"><Bot size={18} /></span>
        <span className="supervisor-title">Superviseur IA</span>
        <span className="supervisor-state" aria-hidden="true">
          {isPending && <Loader2 className="spin" size={14} />}
          {status === 'unavailable' && <WifiOff size={14} />}
          {status === 'connected' && <span className="supervisor-live-dot" />}
        </span>
      </header>
      {statusMessage && <p className="supervisor-connection-status" role="status">{statusMessage}</p>}
      <section className="supervisor-metrics" aria-label="Métriques du quiz">
        <h2>Votre progression</h2>
        {metrics ? <>
        {metricsUnavailable && <p className="supervisor-metrics-empty" role="status">Actualisation des métriques indisponible. Les valeurs affichées peuvent être anciennes.</p>}
        <dl>
          <div><dt>Question actuelle</dt><dd>{secondsRemaining === null ? '—' : `${Math.max(0, metrics.time_limit_seconds - secondsRemaining)} s`}</dd></div>
          <div><dt>Changements de réponse</dt><dd>{metrics.total_answer_changes}</dd></div>
          <div><dt>Signaux d’hésitation</dt><dd>{metrics.hesitation_events}</dd></div>
          <div><dt>Réponses incorrectes</dt><dd>{metrics.incorrect_answers}</dd></div>
          <div><dt>Questions expirées</dt><dd>{metrics.timeout_count}</dd></div>
          <div><dt>Précision</dt><dd>{metrics.accuracy_percent === null ? '—' : `${metrics.accuracy_percent}%`}</dd></div>
          <div><dt>Temps moyen</dt><dd>{metrics.average_response_seconds === null ? '—' : `${metrics.average_response_seconds} s`}</dd></div>
        </dl></> : <p className="supervisor-metrics-empty" role="status">{metricsUnavailable ? 'Métriques indisponibles pour le moment. Vous pouvez continuer le quiz.' : 'Chargement des métriques…'}</p>}
      </section>
      <section className="supervisor-history" aria-label="Activité récente">
        <h2>Activité récente</h2>
        {activity.length ? <ul>{activity.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>Aucune activité récente pour le moment.</p>}
      </section>
      {messages.slice(-1).map((message) => (
        <article
          className={`supervisor-message${message.trigger_type === 'repeated_errors' ? ' is-attention' : ''}`}
          key={message.id}
        >
          <span className="supervisor-message-icon" aria-hidden="true">
            {message.trigger_type === 'repeated_errors' ? <TriangleAlert size={16} /> : <TrendingUp size={16} />}
          </span>
          <div>
            <p>{message.message}</p>
            <span className="supervisor-message-label">
              {message.generation_status === 'FALLBACK'
                ? 'Conseil de secours'
              : message.llm_provider === 'mock'
                ? 'Conseil simulé · fournisseur mock'
                : 'Conseil du superviseur'}
            </span>
          </div>
        </article>
      ))}
      {messages.length > 1 && <details className="supervisor-message-history">
        <summary>Historique des conseils ({messages.length})</summary>
        {messages.slice(0, -1).map((message) => <p key={message.id}>{message.message}</p>)}
      </details>}
    </aside>
  )
}

export default SupervisorFeedback
