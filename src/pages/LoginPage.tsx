import { type FormEvent, useState } from 'react'
import { Eye, EyeOff, Lock, Loader2, LogIn, User as UserIcon } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import { setToken } from '../auth/tokenStorage'
import type { ModerationStatus, User } from '../types'

type LoginResponse = {
  token: string
  user: User
}

type ModerationErrorData = {
  moderation_status?: unknown
}

function isModerationErrorData(value: unknown): value is ModerationErrorData {
  return typeof value === 'object' && value !== null
}

function isModerationStatus(value: unknown): value is ModerationStatus {
  return (
    value === 'PENDING' ||
    value === 'SUSPECT' ||
    value === 'REJETE' ||
    value === 'OK'
  )
}

function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMessage(null)

    if (!username.trim() || !password) {
      setErrorMessage(
        'Le nom d’utilisateur et le mot de passe sont obligatoires.',
      )
      return
    }

    setIsSubmitting(true)
    try {
      const response = await apiFetch<LoginResponse>('/api/auth/login/', {
        method: 'POST',
        body: {
          username: username.trim(),
          password,
        },
      })

      setToken(response.token)
      navigate(response.user.role === 'ADMIN' ? '/admin/moderation' : '/profile')
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 400) {
        setErrorMessage('Identifiants invalides.')
      } else if (error instanceof ApiError && error.status === 403) {
        const data = isModerationErrorData(error.data)
          ? error.data
          : undefined
        const moderationStatus = data?.moderation_status

        if (
          isModerationStatus(moderationStatus) &&
          (moderationStatus === 'SUSPECT' || moderationStatus === 'PENDING')
        ) {
          setErrorMessage(
            'Votre profil est en cours de vérification par un administrateur.',
          )
        } else if (moderationStatus === 'REJETE') {
          setErrorMessage('Votre profil a été refusé.')
        } else {
          setErrorMessage(
            'Une erreur est survenue lors de la connexion. Veuillez réessayer.',
          )
        }
      } else {
        setErrorMessage(
          'Une erreur est survenue lors de la connexion. Veuillez réessayer.',
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="page-shell">
      <section className="auth-card card">
        <div className="auth-heading">
          <div className="auth-icon"><LogIn aria-hidden="true" size={26} /></div>
          <h1>Connexion</h1>
          <p>Retrouvez vos projets et vos collaborations.</p>
        </div>
        {errorMessage && <p className="alert alert-error" role="alert">{errorMessage}</p>}
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
          <label htmlFor="username">Nom d’utilisateur</label>
          <div className="input-with-icon">
            <UserIcon aria-hidden="true" size={18} />
            <input className="form-input" id="username" name="username" type="text" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </div>
          </div>
          <div className="form-group">
          <label htmlFor="password">Mot de passe</label>
          <div className="input-with-icon">
            <Lock aria-hidden="true" size={18} />
            <input className="form-input" id="password" name="password" type={isPasswordVisible ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
            <button className="input-action" type="button" aria-label={isPasswordVisible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setIsPasswordVisible((visible) => !visible)}>
              {isPasswordVisible ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
            </button>
          </div>
          </div>
          <button className="btn btn-primary form-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 className="spin" aria-hidden="true" size={18} />Connexion en cours...</> : 'Se connecter'}
          </button>
        </form>
        <Link className="auth-link" to="/register">Pas encore de compte ? S’inscrire</Link>
      </section>
    </main>
  )
}

export default LoginPage
