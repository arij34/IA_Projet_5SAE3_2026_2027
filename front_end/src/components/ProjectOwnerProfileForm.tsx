import { type FormEvent, useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { ProfileUpdate } from '../types'

type ProjectOwnerProfileFormProps = {
  initialValue: ProfileUpdate
  isSubmitting: boolean
  onSubmit: (value: ProfileUpdate) => void
}

function ProjectOwnerProfileForm({ initialValue, isSubmitting, onSubmit }: ProjectOwnerProfileFormProps) {
  const [title, setTitle] = useState(initialValue.title)
  const [bio, setBio] = useState(initialValue.bio)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors: Record<string, string> = {}
    const trimmedTitle = title.trim()
    const trimmedBio = bio.trim()
    if (!trimmedTitle) nextErrors.title = 'Le nom du projet ou de l’entreprise est obligatoire.'
    if (!trimmedBio) nextErrors.bio = 'La description du projet est obligatoire.'
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    onSubmit({ title: trimmedTitle, bio: trimmedBio, skills: [], hourly_rate: null, cv: null })
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="title">Nom du projet ou de l'entreprise</label>
        <input className="form-input" id="title" name="title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={120} />
        {errors.title && <p className="form-error" role="alert">{errors.title}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="bio">Description du projet</label>
        <textarea className="form-input" id="bio" name="bio" value={bio} onChange={(event) => setBio(event.target.value)} />
        {errors.bio && <p className="form-error" role="alert">{errors.bio}</p>}
      </div>
      <button className="btn btn-primary form-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? <><Loader2 className="spin" aria-hidden="true" size={18} />Enregistrement en cours...</> : 'Enregistrer'}
      </button>
    </form>
  )
}

export default ProjectOwnerProfileForm
