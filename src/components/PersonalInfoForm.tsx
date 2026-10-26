import { type FormEvent, useState } from 'react'
import type { User } from '../types'

type PersonalInfoFormProps = {
  user: User
  isSubmitting: boolean
  serverErrors: Partial<Record<'username' | 'email', string[]>>
  onSubmit: (value: { username: string; email: string }) => void
}

function PersonalInfoForm({ user, isSubmitting, serverErrors, onSubmit }: PersonalInfoFormProps) {
  const [username, setUsername] = useState(user.username)
  const [email, setEmail] = useState(user.email)
  const [errors, setErrors] = useState<Partial<Record<'username' | 'email', string[]>>>({})

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors: Partial<Record<'username' | 'email', string[]>> = {}
    const trimmedUsername = username.trim()
    const trimmedEmail = email.trim()
    if (!trimmedUsername) nextErrors.username = ['Le nom d’utilisateur est obligatoire.']
    if (!trimmedEmail) {
      nextErrors.email = ['L’adresse e-mail est obligatoire.']
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      nextErrors.email = ['L’adresse e-mail n’est pas valide.']
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) onSubmit({ username: trimmedUsername, email: trimmedEmail })
  }

  const fieldErrors = (field: 'username' | 'email') => errors[field] ?? serverErrors[field] ?? []

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="personal-username">Nom d’utilisateur</label>
        <input className="form-input" id="personal-username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        {fieldErrors('username').map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
      </div>
      <div className="form-group">
        <label htmlFor="personal-email">E-mail</label>
        <input className="form-input" id="personal-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" />
        {fieldErrors('email').map((message) => <p className="form-error" role="alert" key={message}>{message}</p>)}
      </div>
      <button className="btn btn-primary form-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Enregistrement en cours...' : 'Enregistrer mes informations'}
      </button>
    </form>
  )
}

export default PersonalInfoForm
