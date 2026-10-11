import { type ChangeEvent, type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import { clearToken, getToken } from '../auth/tokenStorage'
import type { ModerationStatus, Role, User } from '../types'

type ProfileUser = User & {
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
}

type ProfileForm = {
  title: string
  bio: string
  skills: string
  hourly_rate: string
}

type ProfilePayload = {
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
}

type FieldErrors = Partial<Record<keyof ProfileForm, string[]>>

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

function getFieldErrors(data: unknown): FieldErrors {
  if (!isRecord(data)) {
    return {}
  }

  const fields: Array<keyof ProfileForm> = [
    'title',
    'bio',
    'skills',
    'hourly_rate',
  ]
  const errors: FieldErrors = {}
  for (const field of fields) {
    const messages = data[field]
    if (Array.isArray(messages)) {
      const textMessages = messages.filter(
        (message): message is string => typeof message === 'string',
      )
      if (textMessages.length > 0) {
        errors[field] = textMessages
      }
    }
  }
  return errors
}

function getInitialForm(user: ProfileUser): ProfileForm {
  return {
    title: user.title,
    bio: user.bio,
    skills: user.skills.join(', '),
    hourly_rate: user.hourly_rate === null ? '' : String(user.hourly_rate),
  }
}

function ProfilePage() {
  const navigate = useNavigate()
  const [user, setUser] = useState<ProfileUser | null>(null)
  const [form, setForm] = useState<ProfileForm | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoggedOutAfterUpdate, setIsLoggedOutAfterUpdate] = useState(false)

  useEffect(() => {
    let isMounted = true

    const loadProfile = async () => {
      if (!getToken()) {
        if (isMounted) {
          setIsLoading(false)
        }
        navigate('/login', { replace: true })
        return
      }

      try {
        const profile = await apiFetch<ProfileUser>('/api/users/me/')
        if (isMounted) {
          setUser(profile)
          setForm(getInitialForm(profile))
        }
      } catch (error: unknown) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (isMounted) {
          setGeneralError(
            'Une erreur est survenue lors du chargement du profil. Veuillez réessayer.',
          )
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    void loadProfile()
    return () => {
      isMounted = false
    }
  }, [navigate])

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = event.target
    setForm((currentForm) =>
      currentForm === null
        ? currentForm
        : { ...currentForm, [name]: value },
    )
    setFieldErrors((currentErrors) => ({
      ...currentErrors,
      [name]: undefined,
    }))
    setGeneralError(null)
    setSuccessMessage(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (form === null) {
      return
    }

    setFieldErrors({})
    setGeneralError(null)
    setSuccessMessage(null)

    const hourlyRate = form.hourly_rate.trim() === ''
      ? null
      : Number(form.hourly_rate)
    if (hourlyRate !== null && (!Number.isFinite(hourlyRate) || hourlyRate < 0)) {
      setFieldErrors({
        hourly_rate: ['Le tarif horaire doit être un nombre positif ou nul.'],
      })
      return
    }

    const payload: ProfilePayload = {
      title: form.title,
      bio: form.bio,
      skills: form.skills
        .split(',')
        .map((skill) => skill.trim())
        .filter((skill) => skill.length > 0),
      hourly_rate: hourlyRate,
    }

    setIsSubmitting(true)
    try {
      const response = await apiFetch<Partial<ProfileUser>>('/api/users/me/', {
        method: 'PATCH',
        body: payload,
      })
      const status = response.moderation_status

      if (status === 'OK') {
        setSuccessMessage('Profil enregistré.')
      } else {
        clearToken()
        setIsLoggedOutAfterUpdate(true)
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 400) {
        const errors = getFieldErrors(error.data)
        if (Object.keys(errors).length > 0) {
          setFieldErrors(errors)
        } else {
          setGeneralError('Veuillez corriger les informations saisies.')
        }
      } else {
        setGeneralError(
          'Une erreur est survenue lors de l’enregistrement. Veuillez réessayer.',
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleLogout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  if (isLoading) {
    return <p>Chargement...</p>
  }

  if (isLoggedOutAfterUpdate) {
    return (
      <main>
        <p>
          Votre profil modifié est en cours de vérification (ou a été refusé).
          Vous avez été déconnecté.
        </p>
        <Link to="/login">Se connecter</Link>
      </main>
    )
  }

  if (user === null || form === null) {
    return generalError ? <p role="alert">{generalError}</p> : null
  }

  const renderErrors = (field: keyof ProfileForm) =>
    fieldErrors[field]?.map((message) => (
      <p key={message} role="alert">
        {message}
      </p>
    ))

  return (
    <main>
      <h1>Profil</h1>
      {generalError && <p role="alert">{generalError}</p>}
      <section>
        <h2>Informations du compte</h2>
        <p>Nom d’utilisateur : {user.username}</p>
        <p>E-mail : {user.email}</p>
        <p>Rôle : {roleLabels[user.role]}</p>
        <p>
          Statut de modération : {moderationStatusLabels[user.moderation_status]}
        </p>
      </section>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="title">Titre</label>
          <input
            id="title"
            name="title"
            type="text"
            maxLength={120}
            value={form.title}
            onChange={handleChange}
          />
          {renderErrors('title')}
        </div>

        <div>
          <label htmlFor="bio">Biographie</label>
          <textarea id="bio" name="bio" value={form.bio} onChange={handleChange} />
          {renderErrors('bio')}
        </div>

        <div>
          <label htmlFor="skills">Compétences (séparées par des virgules)</label>
          <input
            id="skills"
            name="skills"
            type="text"
            value={form.skills}
            onChange={handleChange}
          />
          {renderErrors('skills')}
        </div>

        <div>
          <label htmlFor="hourly_rate">Tarif horaire</label>
          <input
            id="hourly_rate"
            name="hourly_rate"
            type="number"
            min="0"
            step="any"
            value={form.hourly_rate}
            onChange={handleChange}
          />
          {renderErrors('hourly_rate')}
        </div>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? 'Enregistrement et vérification en cours...'
            : 'Enregistrer'}
        </button>
      </form>

      {successMessage && <p role="status">{successMessage}</p>}
      <button type="button" onClick={handleLogout}>
        Se déconnecter
      </button>
    </main>
  )
}

export default ProfilePage
