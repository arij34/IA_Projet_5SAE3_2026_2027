import {
  type ChangeEvent,
  type FormEvent,
  useState,
} from 'react'
import { CheckCircle2, Eye, EyeOff, Loader2, UserPlus, XCircle, Info } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ApiError, apiFetchFormData } from '../api/client'
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
  cv: File | null
}

type RegisterPayload = {
  username: string
  email: string
  password: string
  role: Exclude<Role, 'ADMIN'>
  title: string
  bio?: string
  skills?: string[]
}

type RegisterResponse = {
  moderation_status: ModerationStatus
}

type FieldErrors = Partial<Record<keyof RegisterForm, string[]>>

const MAX_CV_SIZE = 5 * 1024 * 1024

const initialForm: RegisterForm = {
  username: '',
  email: '',
  password: '',
  passwordConfirmation: '',
  role: 'FREELANCER',
  title: '',
  bio: '',
  skills: '',
  cv: null,
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
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)
  const [isConfirmationVisible, setIsConfirmationVisible] = useState(false)

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = event.target
    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
      ...(name === 'role' && value === 'PROJECT_OWNER' ? { bio: '', skills: '' } : {}),
      ...(name === 'role' && value === 'PROJECT_OWNER' ? { cv: null } : {}),
    }))
    setFieldErrors((currentErrors) => ({
      ...currentErrors,
      [name]: undefined,
    }))
    setGeneralError(null)
  }

  const handleCvChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    setGeneralError(null)
    setFieldErrors((currentErrors) => ({ ...currentErrors, cv: undefined }))

    if (file !== null && (file.type !== 'application/pdf' || !file.name.toLowerCase().endsWith('.pdf'))) {
      setForm((currentForm) => ({ ...currentForm, cv: null }))
      event.target.value = ''
      setFieldErrors((currentErrors) => ({
        ...currentErrors,
        cv: ['Le CV doit être au format PDF.'],
      }))
      return
    }
    if (file !== null && file.size > MAX_CV_SIZE) {
      setForm((currentForm) => ({ ...currentForm, cv: null }))
      event.target.value = ''
      setFieldErrors((currentErrors) => ({
        ...currentErrors,
        cv: ['Le CV ne doit pas dépasser 5 Mo.'],
      }))
      return
    }
    setForm((currentForm) => ({ ...currentForm, cv: file }))
  }

  const removeCv = () => {
    setForm((currentForm) => ({ ...currentForm, cv: null }))
    setFieldErrors((currentErrors) => ({ ...currentErrors, cv: undefined }))
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
      ...(form.role === 'FREELANCER'
        ? {
            bio: form.bio.trim(),
            skills: form.skills.split(',').map((skill) => skill.trim()).filter((skill) => skill.length > 0),
          }
        : {}),
    }
    const formData = new FormData()
    formData.append('username', payload.username)
    formData.append('email', payload.email)
    formData.append('password', payload.password)
    formData.append('role', payload.role)
    formData.append('title', payload.title)
    if (payload.bio !== undefined) {
      formData.append('bio', payload.bio)
    }
    payload.skills?.forEach((skill) => formData.append('skills', skill))
    if (form.cv !== null) {
      formData.append('cv', form.cv)
    }

    setIsSubmitting(true)
    try {
      const response = await apiFetchFormData<RegisterResponse>(
        '/api/auth/register/',
        formData,
        'POST',
      )

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
      <main className="page-shell">
        <section className="status-card card">
          <div className="status-icon success"><CheckCircle2 aria-hidden="true" size={28} /></div>
          <p className="alert alert-success" role="status">Votre compte est validé.</p>
          <Link className="btn btn-primary" to="/login">Se connecter</Link>
        </section>
      </main>
    )
  }

  if (moderationStatus === 'PENDING' || moderationStatus === 'SUSPECT') {
    return (
      <main className="page-shell">
        <section className="status-card card">
          <div className="status-icon info"><Info aria-hidden="true" size={28} /></div>
          <p className="alert alert-info" role="status">
          Votre profil est en cours de vérification par un administrateur. Vous
          pourrez vous connecter une fois qu&apos;il sera accepté.
          </p>
        </section>
      </main>
    )
  }

  if (moderationStatus === 'REJETE') {
    return (
      <main className="page-shell">
        <section className="status-card card">
          <div className="status-icon error"><XCircle aria-hidden="true" size={28} /></div>
          <p className="alert alert-error" role="alert">Votre profil a été refusé.</p>
        </section>
      </main>
    )
  }

  const isFreelancer = form.role === 'FREELANCER'

  return (
    <main className="page-shell">
      <section className="form-card card register-card">
        <div className="auth-heading">
          <div className="auth-icon"><UserPlus aria-hidden="true" size={26} /></div>
          <h1>Créer un compte</h1>
          <p>Rejoignez une communauté de talents et de projets.</p>
        </div>
        {generalError && <p className="alert alert-error" role="alert">{generalError}</p>}
        <form onSubmit={handleSubmit} noValidate>
          <fieldset>
            <legend>Compte</legend>
            <div className="form-grid">
        <div className="form-group">
          <label htmlFor="username">Nom d’utilisateur</label>
          <input className="form-input"
            id="username"
            name="username"
            type="text"
            value={form.username}
            onChange={handleChange}
            autoComplete="username"
          />
          {fieldErrors.username?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>

        <div className="form-group">
          <label htmlFor="email">E-mail</label>
          <input className="form-input"
            id="email"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
          />
          {fieldErrors.email?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>

        <div className="form-group">
          <label htmlFor="password">Mot de passe</label>
          <div className="input-with-icon">
          <input className="form-input"
            id="password"
            name="password"
            type={isPasswordVisible ? 'text' : 'password'}
            value={form.password}
            onChange={handleChange}
            autoComplete="new-password"
          />
          <button className="input-action" type="button" aria-label={isPasswordVisible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setIsPasswordVisible((visible) => !visible)}>{isPasswordVisible ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}</button>
          </div>
          {fieldErrors.password?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>

        <div className="form-group">
          <label htmlFor="passwordConfirmation">
            Confirmation du mot de passe
          </label>
          <div className="input-with-icon">
          <input className="form-input"
            id="passwordConfirmation"
            name="passwordConfirmation"
            type={isConfirmationVisible ? 'text' : 'password'}
            value={form.passwordConfirmation}
            onChange={handleChange}
            autoComplete="new-password"
          />
          <button className="input-action" type="button" aria-label={isConfirmationVisible ? 'Masquer la confirmation' : 'Afficher la confirmation'} onClick={() => setIsConfirmationVisible((visible) => !visible)}>{isConfirmationVisible ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}</button>
          </div>
          {fieldErrors.passwordConfirmation?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Profil</legend>
            <div className="form-grid">
        <div className="form-group">
          <label htmlFor="role">Rôle</label>
          <select className="form-input" id="role" name="role" value={form.role} onChange={handleChange}>
            <option value="FREELANCER">Freelance</option>
            <option value="PROJECT_OWNER">Porteur de projet</option>
          </select>
          {fieldErrors.role?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>

        <div className="form-group">
          <label htmlFor="title">Titre</label>
          <input className="form-input"
            id="title"
            name="title"
            type="text"
            maxLength={120}
            value={form.title}
            onChange={handleChange}
          />
          {fieldErrors.title?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>

        {isFreelancer && <div className="form-group form-full">
          <label htmlFor="bio">Biographie</label>
          <textarea className="form-input" id="bio" name="bio" value={form.bio} onChange={handleChange} />
          {fieldErrors.bio?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>}

        {isFreelancer && <div className="form-group form-full">
          <label htmlFor="skills">Compétences (séparées par des virgules)</label>
          <input className="form-input"
            id="skills"
            name="skills"
            type="text"
            value={form.skills}
            onChange={handleChange}
          />
          <small className="field-hint">Séparées par des virgules</small>
          {fieldErrors.skills?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>}

        {isFreelancer && <div className="form-group form-full">
          <label htmlFor="cv">Importer mon CV</label>
          <input className="form-input" id="cv" name="cv" type="file" accept="application/pdf,.pdf" onChange={handleCvChange} />
          {form.cv !== null && <div className="file-selection">
            <span>{form.cv.name}</span>
            <button className="btn btn-secondary" type="button" onClick={removeCv}>Retirer</button>
          </div>}
          <small className="field-hint">PDF uniquement, 5 Mo maximum.</small>
          {fieldErrors.cv?.map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
        </div>}
            </div>
          </fieldset>

          <button className="btn btn-primary form-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 className="spin" aria-hidden="true" size={18} />Vérification de votre profil en cours...</> : 'S’inscrire'}
          </button>
        </form>
        <Link className="auth-link" to="/login">Déjà un compte ? Se connecter</Link>
      </section>
    </main>
  )
}

export default RegisterPage
