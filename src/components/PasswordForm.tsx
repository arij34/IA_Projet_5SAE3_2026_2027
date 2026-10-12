import { type FormEvent, useState } from 'react'
import { changePassword, ApiError } from '../api/client'

type PasswordFormProps = {
  isSubmitting: boolean
  onSubmittingChange: (isSubmitting: boolean) => void
}

function PasswordForm({ isSubmitting, onSubmittingChange }: PasswordFormProps) {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMessage(null)
    setSuccessMessage(null)
    if (!oldPassword) {
      setErrorMessage('L’ancien mot de passe est obligatoire.')
      return
    }
    if (newPassword.length < 8) {
      setErrorMessage('Le nouveau mot de passe doit contenir au moins 8 caractères.')
      return
    }
    if (newPassword !== confirmation) {
      setErrorMessage('Les deux nouveaux mots de passe doivent être identiques.')
      return
    }
    onSubmittingChange(true)
    try {
      await changePassword({ oldPassword, newPassword })
      setOldPassword('')
      setNewPassword('')
      setConfirmation('')
      setSuccessMessage('Mot de passe modifié.')
    } catch (error: unknown) {
      setErrorMessage(error instanceof ApiError && error.status === 400
        ? 'L’ancien mot de passe est incorrect ou les données sont invalides.'
        : error instanceof Error ? error.message : 'Impossible de modifier le mot de passe.')
    } finally {
      onSubmittingChange(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {errorMessage && <p className="alert alert-error" role="alert">{errorMessage}</p>}
      {successMessage && <p className="alert alert-success" role="status">{successMessage}</p>}
      <div className="form-group"><label htmlFor="old-password">Ancien mot de passe</label><input className="form-input" id="old-password" type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} autoComplete="current-password" /></div>
      <div className="form-group"><label htmlFor="new-password">Nouveau mot de passe</label><input className="form-input" id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" /><small className="field-hint">Minimum 8 caractères.</small></div>
      <div className="form-group"><label htmlFor="password-confirmation">Confirmation du nouveau mot de passe</label><input className="form-input" id="password-confirmation" type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" /></div>
      <button className="btn btn-secondary form-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Modification en cours...' : 'Changer mon mot de passe'}</button>
    </form>
  )
}

export default PasswordForm
