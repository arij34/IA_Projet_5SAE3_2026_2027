import { useSupervisorChannel } from '../hooks/useSupervisorChannel'
import type { SupervisorConnectionStatus } from '../types/challenges'

function connectionMessage(status: SupervisorConnectionStatus): string | null {
  if (status === 'connecting') return 'Connexion au superviseur…'
  if (status === 'reconnecting') return 'Connexion interrompue. Nouvelle tentative…'
  if (status === 'unavailable') {
    return 'Les conseils du superviseur sont indisponibles. Vous pouvez continuer le quiz.'
  }
  if (status === 'connected') {
    return 'Superviseur actif. Un conseil peut apparaître après plusieurs réponses consécutives.'
  }
  return null
}

function SupervisorFeedback({ attemptId }: { attemptId: number }) {
  const { messages, status } = useSupervisorChannel(attemptId)
  const statusMessage = messages.length === 0 || status !== 'connected'
    ? connectionMessage(status)
    : null

  return (
    <section className="supervisor-feedback" aria-label="Conseils du superviseur">
      {statusMessage && <p className="supervisor-connection-status" role="status">{statusMessage}</p>}
      {messages.map((message) => (
        <article className="supervisor-message" key={message.id}>
          <p>{message.message}</p>
          <span>
            {message.generation_status === 'FALLBACK'
              ? 'Conseil de secours'
              : 'Conseil du superviseur'}
          </span>
        </article>
      ))}
    </section>
  )
}

export default SupervisorFeedback
