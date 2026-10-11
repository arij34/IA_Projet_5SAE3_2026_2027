import {
  type ChangeEvent,
  type FormEvent,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import type { ModerationStatus, Role } from '../types'

type RegisterForm = {
  username: string
  email: string
  password: string
  passwordConfirmation: string
  role: Exclude<Role, 'ADMIN'>
  title: string
  bio: string
  skills: string
}

type RegisterPayload = {
  username: string
  email: string
  password: string
  role: Exclude<Role, 'ADMIN'>
  title: string
  bio: string
  skills: string[]
}

type RegisterResponse = {
  moderation_status: ModerationStatus
}

type FieldErrors = Partial<Record<keyof RegisterForm, string[]>>

const initialForm: RegisterForm = {
  username: '',
  email: '',
  password: '',
  passwordConfirmation: '',
  role: 'FREELANCER',
  title: '',
  bio: '',
  skills: '',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getFieldErrors(data: unknown): FieldErrors {
  if (!isRecord(data)) {
    return {}
  }

  const errors: FieldErrors = {}
  for (const field of Object.keys(initialForm) as Array<keyof RegisterForm>) {
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

function isModerationStatus(value: unknown): value is ModerationStatus {
  return (
    value === 'OK' ||
    value === 'PENDING' ||
    value === 'SUSPECT' ||
    value === 'REJETE'
  )
}

function RegisterPage() {
  const [form, setForm] = useState<RegisterForm>(initialForm)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [moderationStatus, setModerationStatus] =
    useState<ModerationStatus | null>(null)

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = event.target
    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }))
    setFieldErrors((currentErrors) => ({
      ...currentErrors,
      [name]: undefined,
    }))
    setGeneralError(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFieldErrors({})
    setGeneralError(null)

    const localErrors: FieldErrors = {}
    if (!form.username.trim()) {
      localErrors.username = ['Le nom d’utilisateur est obligatoire.']
    }
    if (!form.email.trim()) {
      localErrors.email = ['L’adresse e-mail est obligatoire.']
    }
    if (!form.password.trim()) {
      localErrors.password = ['Le mot de passe est obligatoire.']
    }
    if (form.password !== form.passwordConfirmation) {
      localErrors.passwordConfirmation = [
        'Les deux mots de passe doivent être identiques.',
      ]
    }

    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors)
      return
    }

    const payload: RegisterPayload = {
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      role: form.role,
      title: form.title.trim(),
      bio: form.bio.trim(),
      skills: form.skills
        .split(',')
        .map((skill) => skill.trim())
        .filter((skill) => skill.length > 0),
    }

    setIsSubmitting(true)
    try {
      const response = await apiFetch<RegisterResponse>('/api/auth/register/', {
        method: 'POST',
        body: payload,
      })

      if (!isModerationStatus(response.moderation_status)) {
        setGeneralError('La réponse du serveur est invalide.')
        return
      }
      setModerationStatus(response.moderation_status)
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
          'Une erreur est survenue lors de l’inscription. Veuillez réessayer.',
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (moderationStatus === 'OK') {
    return (
      <main>
        <h1>Votre compte est validé.</h1>
        <Link to="/login">Se connecter</Link>
      </main>
    )
  }

  if (moderationStatus === 'PENDING' || moderationStatus === 'SUSPECT') {
    return (
      <main>
        <h1>
          Votre profil est en cours de vérification par un administrateur. Vous
          pourrez vous connecter une fois qu&apos;il sera accepté.
        </h1>
      </main>
    )
  }

  if (moderationStatus === 'REJETE') {
    return (
      <main>
        <h1>Votre profil a été refusé.</h1>
      </main>
    )
  }

  const renderErrors = (field: keyof RegisterForm) =>
    fieldErrors[field]?.map((message) => (
      <p key={message} role="alert">
        {message}
      </p>
    ))

  return (
    <main>
      <h1>Inscription</h1>
      {generalError && <p role="alert">{generalError}</p>}
      <form onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="username">Nom d’utilisateur</label>
          <input
            id="username"
            name="username"
            type="text"
            value={form.username}
            onChange={handleChange}
            autoComplete="username"
          />
          {renderErrors('username')}
        </div>

        <div>
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
          />
          {renderErrors('email')}
        </div>

        <div>
          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            autoComplete="new-password"
          />
          {renderErrors('password')}
        </div>

        <div>
          <label htmlFor="passwordConfirmation">
            Confirmation du mot de passe
          </label>
          <input
            id="passwordConfirmation"
            name="passwordConfirmation"
            type="password"
            value={form.passwordConfirmation}
            onChange={handleChange}
            autoComplete="new-password"
          />
          {renderErrors('passwordConfirmation')}
        </div>

        <div>
          <label htmlFor="role">Rôle</label>
          <select id="role" name="role" value={form.role} onChange={handleChange}>
            <option value="FREELANCER">Freelance</option>
            <option value="PROJECT_OWNER">Porteur de projet</option>
          </select>
          {renderErrors('role')}
        </div>

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

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? 'Vérification de votre profil en cours...'
            : 'S’inscrire'}
        </button>
      </form>
      <Link to="/login">Déjà un compte ? Se connecter</Link>
    </main>
  )
}

export default RegisterPage
