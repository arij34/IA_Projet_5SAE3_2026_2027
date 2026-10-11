import { useEffect, useState } from 'react'
import { Check, Eye, ShieldCheck, Trash2, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
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

  if (isLoading) {
    return <main className="page-shell"><p className="loading-state">Chargement...</p></main>
  }

  if (errorMessage && profiles.length === 0) {
    return (
      <main className="page-shell">
        <section className="status-card card">
          <p className="alert alert-error" role="alert">{errorMessage}</p>
        </section>
      </main>
    )
  }

  return (
    <main className="page-shell admin-page">
      <div className="admin-heading">
        <div className="admin-title-icon"><ShieldCheck aria-hidden="true" size={28} /></div>
        <div><h1>Modération des profils</h1><p>Vérifiez les profils avant leur mise en relation.</p></div>
      </div>
      {errorMessage && <p className="alert alert-error" role="alert">{errorMessage}</p>}

      <div className="filter-bar">
        <div className="form-group">
          <label htmlFor="status-filter">Filtrer par statut</label>
          <select className="form-input" id="status-filter" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value as StatusFilter)}>
        <option value="SUSPECT_PENDING">Suspects et en attente</option>
        <option value="ALL">Tous les statuts</option>
        <option value="SUSPECT">Suspect</option>
        <option value="PENDING">En attente</option>
        <option value="OK">Validé</option>
        <option value="REJETE">Refusé</option>
          </select>
        </div>
        <span className="profile-count">{visibleProfiles.length} profil(s)</span>
      </div>

      {visibleProfiles.length === 0 ? (
        <div className="empty-state card"><ShieldCheck aria-hidden="true" size={30} /><p>Aucun profil à afficher.</p></div>
      ) : (
      <div className="table-wrapper">
      <table className="table">
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
              <td><span className={`badge badge-${profile.moderation_status.toLowerCase()}`}>{moderationStatusLabels[profile.moderation_status]}</span></td>
              <td>
                <div className="action-buttons">
                <button className="btn btn-secondary btn-small" type="button" disabled={actionInProgress !== null} onClick={() => void handleViewDetails(profile.id)}>
                  <Eye aria-hidden="true" size={16} />
                  Voir le détail
                </button>
                <button className="btn btn-primary btn-small" type="button" disabled={actionInProgress !== null} onClick={() => void handleApprove(profile.id)}>
                  <Check aria-hidden="true" size={16} />
                  Accepter
                </button>
                <button className="btn btn-danger btn-small" type="button" disabled={actionInProgress !== null} onClick={() => void handleDelete(profile.id)}>
                  <Trash2 aria-hidden="true" size={16} />
                  Supprimer
                </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      )}

      {selectedProfile && (
        <section className="card detail-card">
          <div className="detail-heading"><h2>Détail du profil</h2><button className="icon-button" type="button" aria-label="Fermer le détail" onClick={() => setSelectedProfile(null)}><X aria-hidden="true" size={20} /></button></div>
          <p>Biographie : {selectedProfile.bio}</p>
          <p>Compétences :</p>
          <div className="tag-list">{selectedProfile.skills.map((skill) => <span className="badge badge-neutral" key={skill}>{skill}</span>)}</div>
          <p>
            Tarif horaire :{' '}
            {selectedProfile.hourly_rate === null
              ? 'Non renseigné'
              : selectedProfile.hourly_rate}
          </p>
        </section>
      )}
    </main>
  )
}

export default AdminModerationPage
