import { useEffect, useState } from 'react'
import { Briefcase, Mail, User as UserIcon } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, apiFetch, normalizeProfilePayload } from '../api/client'
import PersonalInfoForm from '../components/PersonalInfoForm'
import PasswordForm from '../components/PasswordForm'
import ProfileForm from '../components/ProfileForm'
import ProfileView from '../components/ProfileView'
import { useAuth } from '../auth/useAuth'
import { clearToken, getToken } from '../auth/tokenStorage'
import type { ModerationStatus, ProfileUpdate, ProfileUser, Role } from '../types'

const roleLabels: Record<Role, string> = {
  FREELANCER: 'Freelance',
  PROJECT_OWNER: 'Porteur de projet',
  ADMIN: 'Administrateur',
}

const moderationStatusLabels: Record<ModerationStatus, string> = {
  OK: 'Validé',
  PENDING: 'En attente',
  SUSPECT: 'En vérification',
  REJETE: 'Refusé',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getServerError(data: unknown): string {
  if (typeof data === 'string' && data.trim()) return data
  if (!isRecord(data)) return 'Veuillez corriger les informations saisies.'
  const messages = Object.entries(data).flatMap(([field, value]) => {
    if (typeof value === 'string' && value.trim()) return [`${field} : ${value}`]
    if (Array.isArray(value)) {
      return value
        .filter((message): message is string => typeof message === 'string' && message.trim().length > 0)
        .map((message) => `${field} : ${message}`)
    }
    return []
  })
  return messages.join(' ; ') || JSON.stringify(data)
}

function ProfilePage() {
  const navigate = useNavigate()
  const { setUser: setAuthenticatedUser } = useAuth()
  const [user, setUser] = useState<ProfileUser | null>(null)
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoggedOutAfterUpdate, setIsLoggedOutAfterUpdate] = useState(false)
  const [isPersonalInfoSubmitting, setIsPersonalInfoSubmitting] = useState(false)
  const [personalInfoErrors, setPersonalInfoErrors] = useState<Partial<Record<'username' | 'email', string[]>>>({})
  const [personalInfoError, setPersonalInfoError] = useState<string | null>(null)
  const [personalInfoSuccess, setPersonalInfoSuccess] = useState<string | null>(null)
  const [isPasswordSubmitting, setIsPasswordSubmitting] = useState(false)

  useEffect(() => {
    let isMounted = true
    const loadProfile = async () => {
      if (!getToken()) {
        setIsLoading(false)
        navigate('/login', { replace: true })
        return
      }
      try {
        const profile = await apiFetch<ProfileUser>('/api/users/me/')
        if (isMounted) {
          setUser(profile)
          setAuthenticatedUser(profile)
        }
      } catch (error: unknown) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (isMounted) {
          setGeneralError('Une erreur est survenue lors du chargement du profil. Veuillez réessayer.')
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    void loadProfile()
    return () => { isMounted = false }
  }, [navigate, setAuthenticatedUser])

  const handlePersonalInfoSubmit = async (value: { username: string; email: string }) => {
    if (user === null) return
    const currentUser: ProfileUser = user
    setPersonalInfoErrors({})
    setPersonalInfoError(null)
    setPersonalInfoSuccess(null)
    setIsPersonalInfoSubmitting(true)
    try {
      const response = await apiFetch<Partial<ProfileUser>>('/api/users/me/', {
        method: 'PATCH',
        body: value,
      })
      const updated: ProfileUser = {
        ...currentUser,
        username: response.username ?? value.username,
        email: response.email ?? value.email,
        title: response.title ?? currentUser.title,
        bio: response.bio ?? currentUser.bio,
        skills: response.skills ?? currentUser.skills,
        hourly_rate: response.hourly_rate ?? currentUser.hourly_rate,
        cv: response.cv ?? currentUser.cv,
        id: response.id ?? currentUser.id,
        role: response.role ?? currentUser.role,
        moderation_status: response.moderation_status ?? currentUser.moderation_status,
      }
      setUser(updated)
      setAuthenticatedUser(updated)
      setPersonalInfoSuccess('Informations personnelles enregistrées.')
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 400 && isRecord(error.data)) {
        const errors: Partial<Record<'username' | 'email', string[]>> = {}
        for (const field of ['username', 'email'] as const) {
          const messages = error.data[field]
          if (Array.isArray(messages)) {
            const textMessages = messages.filter((message): message is string => typeof message === 'string')
            if (textMessages.length > 0) errors[field] = textMessages
          } else if (typeof messages === 'string') {
            errors[field] = [messages]
          }
        }
        setPersonalInfoErrors(errors)
        if (Object.keys(errors).length === 0) setPersonalInfoError(getServerError(error.data))
      } else {
        setPersonalInfoError('Une erreur est survenue lors de l’enregistrement. Veuillez réessayer.')
      }
    } finally {
      setIsPersonalInfoSubmitting(false)
    }
  }

  const handleSubmit = async (value: ProfileUpdate) => {
    if (user === null) return
    setGeneralError(null)
    setSuccessMessage(null)
    setIsSubmitting(true)
    try {
      const payload = normalizeProfilePayload({
        title: value.title,
        bio: value.bio,
        skills: value.skills,
        hourly_rate: value.hourly_rate,
      })
      console.log('Payload envoyé :', payload)
      const response = await apiFetch<Partial<ProfileUser>>('/api/users/me/', {
        method: 'PATCH',
        body: payload,
      })
      console.log('Réponse Django :', response)

      if (response.moderation_status !== 'OK') {
        clearToken()
        setIsLoggedOutAfterUpdate(true)
        return
      }
      setUser((current) => current === null ? current : {
        ...current,
        ...response,
        title: value.title,
        bio: value.bio,
        skills: value.skills,
        hourly_rate: value.hourly_rate,
        cv: response.cv ?? current.cv,
      })
      setSuccessMessage('Profil enregistré.')
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 400) {
        console.error('Réponse Django :', error.data)
        setGeneralError(getServerError(error.data))
      } else if (error instanceof Error) {
        setGeneralError(error.message)
      } else {
        setGeneralError('Une erreur est survenue lors de l’enregistrement. Veuillez réessayer.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isLoading) return <main className="page-shell"><p className="loading-state">Chargement...</p></main>

  if (isLoggedOutAfterUpdate) {
    return (
      <main className="page-shell">
        <section className="status-card card">
          <p className="alert alert-info" role="status">Votre profil modifié est en cours de vérification (ou a été refusé). Vous avez été déconnecté.</p>
          <Link className="btn btn-secondary" to="/login">Se connecter</Link>
        </section>
      </main>
    )
  }

  if (user === null) {
    return <main className="page-shell"><p className="alert alert-error" role="alert">{generalError ?? 'Profil introuvable.'}</p></main>
  }

  return (
    <main className="page-shell profile-page">
      <header className="profile-hero">
        <div className="profile-hero-glow" aria-hidden="true" />
        <div className="profile-heading">
          <div className="avatar">{user.username.charAt(0).toUpperCase()}</div>
          <div><span className="profile-eyebrow">Espace personnel</span><h1>{user.username}</h1><p>{user.email}</p></div>
          <span className={`badge badge-${user.moderation_status.toLowerCase()}`}>{moderationStatusLabels[user.moderation_status]}</span>
        </div>
        <div className="profile-hero-line"><span>Votre profil Freelancy</span><span className="profile-role">{roleLabels[user.role]}</span></div>
      </header>
      {generalError && <p className="alert alert-error" role="alert">{generalError}</p>}
      {personalInfoError && <p className="alert alert-error" role="alert">{personalInfoError}</p>}
      <div className="profile-layout">
        <aside className="profile-sidebar">
          <section className="card account-card profile-card-animated">
          <h2>Mes informations</h2>
          <div className="account-row"><UserIcon aria-hidden="true" size={19} /><span><strong>Nom d’utilisateur</strong>{user.username}</span></div>
          <div className="account-row"><Mail aria-hidden="true" size={19} /><span><strong>E-mail</strong>{user.email}</span></div>
          <div className="account-row"><Briefcase aria-hidden="true" size={19} /><span><strong>Rôle</strong>{roleLabels[user.role]}</span></div>
          </section>
          <section className="card profile-card-animated profile-summary-card">
            <ProfileView user={user} />
          </section>
        </aside>
        <div className="profile-main">
          <section className="card personal-info-card profile-card-animated">
            <div className="section-heading-inline"><div><span className="profile-eyebrow">Compte</span><h2>Mes informations personnelles</h2></div><span className="section-number">01</span></div>
            <p className="field-hint">Le rôle et le statut de modération sont en lecture seule.</p>
            <PersonalInfoForm key={`${user.username}-${user.email}`} user={user} isSubmitting={isPersonalInfoSubmitting} serverErrors={personalInfoErrors} onSubmit={(value) => void handlePersonalInfoSubmit(value)} />
            {personalInfoSuccess && <p className="alert alert-success" role="status">{personalInfoSuccess}</p>}
          </section>
          {user.role !== 'ADMIN' && <section className="card profile-card-animated">
            <div className="section-heading-inline"><div><span className="profile-eyebrow">Profil public</span><h2>Modifier mon profil</h2></div><span className="section-number">02</span></div>
            <ProfileForm user={user} isSubmitting={isSubmitting} onSubmit={(value) => void handleSubmit(value)} />
            {successMessage && <p className="alert alert-success" role="status">{successMessage}</p>}
          </section>}
          <section className="card password-card profile-card-animated">
            <div className="section-heading-inline"><div><span className="profile-eyebrow">Sécurité</span><h2>Changer mon mot de passe</h2></div><span className="section-number">{user.role === 'ADMIN' ? '02' : '03'}</span></div>
            <PasswordForm isSubmitting={isPasswordSubmitting} onSubmittingChange={setIsPasswordSubmitting} />
          </section>
        </div>
      </div>
    </main>
  )
}

export default ProfilePage
