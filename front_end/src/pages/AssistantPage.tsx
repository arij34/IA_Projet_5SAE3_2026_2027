import { type FormEvent, useState } from 'react'
import { Loader2, Send, Sparkles, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ApiError, askChatbot, MAX_CHATBOT_QUESTION_CHARS } from '../api/projects'
import type { ChatbotResponse } from '../types/project'

type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: string[]
  simulated?: boolean
  isError?: boolean
}

const GENERIC_ERROR_MESSAGE = 'Une erreur est survenue. Veuillez réessayer.'

function AssistantPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isSending, setIsSending] = useState(false)

  const addMessage = (message: Omit<Message, 'id'>) => {
    setMessages((current) => [...current, { ...message, id: crypto.randomUUID() }])
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || isSending || trimmedQuestion.length > MAX_CHATBOT_QUESTION_CHARS) return

    addMessage({ role: 'user', text: trimmedQuestion })
    setQuestion('')
    setIsSending(true)

    try {
      const response: ChatbotResponse = await askChatbot(trimmedQuestion)
      if (response.error) {
        addMessage({ role: 'assistant', text: 'Le chatbot est momentanément indisponible.', isError: true })
      } else {
        addMessage({
          role: 'assistant',
          text: typeof response.answer === 'string' ? response.answer : 'Le chatbot n’a pas fourni de réponse.',
          sources: Array.isArray(response.sources) ? response.sources : [],
          simulated: response.simulated === true,
        })
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === 401) {
        navigate('/login', { replace: true })
      } else if (error instanceof ApiError && error.code === 403) {
        addMessage({ role: 'assistant', text: 'Cette fonctionnalité est réservée aux porteurs de projet.', isError: true })
      } else if (error instanceof ApiError && error.code === 429) {
        addMessage({ role: 'assistant', text: 'Trop de questions, réessayez plus tard.', isError: true })
      } else {
        addMessage({ role: 'assistant', text: GENERIC_ERROR_MESSAGE, isError: true })
      }
    } finally {
      setIsSending(false)
    }
  }

  return (
    <main className="page-shell">
      <section className="card page-card">
        <div className="auth-heading">
          <div className="auth-icon"><Sparkles aria-hidden="true" size={26} /></div>
          <h1>Assistant projet</h1>
          <p>Posez une question sur vos projets et les ressources disponibles.</p>
        </div>

        <div aria-live="polite" aria-label="Conversation avec l’assistant" style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.25rem' }}>
          {messages.length === 0 && <p className="empty-state">Aucune question posée pour le moment.</p>}
          {messages.map((message) => (
            <article className={`analysis-panel${message.role === 'user' ? ' user-message' : ''}`} key={message.id}>
              <strong>{message.role === 'user' ? <><UserRound aria-hidden="true" size={16} /> Vous</> : <><Sparkles aria-hidden="true" size={16} /> Assistant</>}</strong>
              <p>{message.text}</p>
              {message.isError !== true && message.simulated === true && <span className="badge badge-suspect">Réponse simulée</span>}
              {message.sources && message.sources.length > 0 && (
                <div className="form-row" aria-label="Sources utilisées">
                  {message.sources.map((source, index) => <span className="badge badge-neutral" key={`${source}-${index}`}>{source}</span>)}
                </div>
              )}
            </article>
          ))}
          {isSending && <p className="loading-state"><Loader2 className="spin" aria-hidden="true" size={18} /> Recherche en cours...</p>}
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="chatbot-question">Votre question</label>
            <textarea
              className="form-input"
              id="chatbot-question"
              maxLength={MAX_CHATBOT_QUESTION_CHARS}
              rows={4}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={isSending}
            />
            <small>{question.length}/{MAX_CHATBOT_QUESTION_CHARS} caractères</small>
          </div>
          <button className="btn btn-primary" type="submit" disabled={isSending || !question.trim() || question.trim().length > MAX_CHATBOT_QUESTION_CHARS}>
            {isSending ? <><Loader2 className="spin" aria-hidden="true" size={18} /> Envoi...</> : <><Send aria-hidden="true" size={17} /> Envoyer</>}
          </button>
        </form>
      </section>
    </main>
  )
}

export default AssistantPage
