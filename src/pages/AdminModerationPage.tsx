import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import { clearToken, getToken } from '../auth/tokenStorage'
import type { ModerationStatus, Role } from '../types'

type ModerationProfile = {
  id: number
  username: string
  email: string
  role: Role
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
  moderation_status: ModerationStatus
}

type StatusFilter = 'SUSPECT_PENDING' | ModerationStatus | 'ALL'

const roleLabels: Record<Role, string> = {
  FREELANCER: 'Freelance',
  PROJECT_OWNER: 'Porteur de projet',
  ADMIN: 'Administrateur',
}

const moderationStatusLabels: Record<ModerationStatus, string> = {
  OK: 'Validé',
  SUSPECT: 'Suspect',
  PENDING: 'En attente',
  REJETE: 'Refusé',
}

function AdminModerationPage() {
  const navigate = useNavigate()
  const [profiles, setProfiles] = useState<ModerationProfile[]>([])
  const [selectedStatus, setSelectedStatus] =
    useState<StatusFilter>('SUSPECT_PENDING')
  const [selectedProfile, setSelectedProfile] =
    useState<ModerationProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    const loadProfiles = async () => {
      if (!getToken()) {
        navigate('/login', { replace: true })
        return
      }

      try {
        const response = await apiFetch<ModerationProfile[]>(
          '/api/admin/moderation/',
        )
        if (isMounted) {
          setProfiles(response)
        }
      } catch (error: unknown) {
        if (error instanceof ApiError && error.status === 401) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (isMounted && error instanceof ApiError && error.status === 403) {
          setErrorMessage('Accès réservé aux administrateurs.')
        } else if (isMounted) {
          setErrorMessage(
            'Une erreur est survenue lors du chargement des profils. Veuillez réessayer.',
          )
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    void loadProfiles()
    return () => {
      isMounted = false
    }
  }, [navigate])

  const visibleProfiles = profiles.filter((profile) => {
    if (selectedStatus === 'ALL') {
      return true
    }
    if (selectedStatus === 'SUSPECT_PENDING') {
      return (
        profile.moderation_status === 'SUSPECT' ||
        profile.moderation_status === 'PENDING'
      )
    }
    return profile.moderation_status === selectedStatus
  })

  const showActionError = (message: string) => {
    setErrorMessage(message)
  }

  const handleViewDetails = async (profileId: number) => {
    setActionInProgress(`detail-${profileId}`)
    setErrorMessage(null)
    try {
      const profile = await apiFetch<ModerationProfile>(
        `/api/admin/moderation/${profileId}/`,
      )
      setSelectedProfile(profile)
    } catch {
      showActionError(
        'Une erreur est survenue lors du chargement du détail. Veuillez réessayer.',
      )
    } finally {
      setActionInProgress(null)
    }
  }

  const handleApprove = async (profileId: number) => {
    setActionInProgress(`approve-${profileId}`)
    setErrorMessage(null)
    try {
      await apiFetch<ModerationProfile>(
        `/api/admin/moderation/${profileId}/approve/`,
        { method: 'POST' },
      )
      setProfiles((currentProfiles) =>
        currentProfiles.map((profile) =>
          profile.id === profileId
            ? { ...profile, moderation_status: 'OK' }
            : profile,
        ),
      )
      setSelectedProfile((currentProfile) =>
        currentProfile?.id === profileId
          ? { ...currentProfile, moderation_status: 'OK' }
          : currentProfile,
      )
    } catch {
      showActionError(
        'Une erreur est survenue lors de l’acceptation du profil. Veuillez réessayer.',
      )
    } finally {
      setActionInProgress(null)
    }
  }

  const handleDelete = async (profileId: number) => {
    if (!window.confirm('Voulez-vous vraiment supprimer ce profil ?')) {
      return
    }

    setActionInProgress(`delete-${profileId}`)
    setErrorMessage(null)
    try {
      await apiFetch<void>(`/api/admin/moderation/${profileId}/`, {
        method: 'DELETE',
      })
      setProfiles((currentProfiles) =>
        currentProfiles.filter((profile) => profile.id !== profileId),
      )
      setSelectedProfile((currentProfile) =>
        currentProfile?.id === profileId ? null : currentProfile,
      )
    } catch {
      showActionError(
        'Une erreur est survenue lors de la suppression du profil. Veuillez réessayer.',
      )
    } finally {
      setActionInProgress(null)
    }
  }

  const handleLogout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  if (isLoading) {
    return <p>Chargement...</p>
  }

  if (errorMessage && profiles.length === 0) {
    return (
      <main>
        <p role="alert">{errorMessage}</p>
        <button type="button" onClick={handleLogout}>
          Se déconnecter
        </button>
      </main>
    )
  }

  return (
    <main>
      <h1>Modération administrateur</h1>
      {errorMessage && <p role="alert">{errorMessage}</p>}

      <label htmlFor="status-filter">Filtrer par statut</label>
      <select
        id="status-filter"
        value={selectedStatus}
        onChange={(event) =>
          setSelectedStatus(event.target.value as StatusFilter)
        }
      >
        <option value="SUSPECT_PENDING">Suspects et en attente</option>
        <option value="ALL">Tous les statuts</option>
        <option value="SUSPECT">Suspect</option>
        <option value="PENDING">En attente</option>
        <option value="OK">Validé</option>
        <option value="REJETE">Refusé</option>
      </select>

      <table>
        <thead>
          <tr>
            <th scope="col">Nom d’utilisateur</th>
            <th scope="col">E-mail</th>
            <th scope="col">Rôle</th>
            <th scope="col">Titre</th>
            <th scope="col">Statut</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {visibleProfiles.map((profile) => (
            <tr key={profile.id}>
              <td>{profile.username}</td>
              <td>{profile.email}</td>
              <td>{roleLabels[profile.role]}</td>
              <td>{profile.title}</td>
              <td>{moderationStatusLabels[profile.moderation_status]}</td>
              <td>
                <button
                  type="button"
                  disabled={actionInProgress !== null}
                  onClick={() => void handleViewDetails(profile.id)}
                >
                  Voir le détail
                </button>
                <button
                  type="button"
                  disabled={actionInProgress !== null}
                  onClick={() => void handleApprove(profile.id)}
                >
                  Accepter
                </button>
                <button
                  type="button"
                  disabled={actionInProgress !== null}
                  onClick={() => void handleDelete(profile.id)}
                >
                  Supprimer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedProfile && (
        <section>
          <h2>Détail du profil</h2>
          <p>Biographie : {selectedProfile.bio}</p>
          <p>Compétences : {selectedProfile.skills.join(', ')}</p>
          <p>
            Tarif horaire :{' '}
            {selectedProfile.hourly_rate === null
              ? 'Non renseigné'
              : selectedProfile.hourly_rate}
          </p>
          <button type="button" onClick={() => setSelectedProfile(null)}>
            Fermer le détail
          </button>
        </section>
      )}

      <button type="button" onClick={handleLogout}>
        Se déconnecter
      </button>
      <Link to="/profile">Mon profil</Link>
    </main>
  )
}

export default AdminModerationPage
