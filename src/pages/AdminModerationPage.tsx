import { AlertTriangle, Check, CheckCircle2, Eye, Loader2, ShieldCheck, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import { clearToken, getToken } from '../auth/tokenStorage'
import type { AnalysisDecision, ModerationAnalysis, ModerationCriterion, ModerationProfile, ModerationStatus, Role } from '../types'

type StatusFilter = 'SUSPECT_PENDING' | ModerationStatus | 'ALL'
type RoleFilter = Role | 'ALL'
type ErrorContext = 'load' | 'detail' | 'analyze' | 'approve' | 'delete'

const roleLabels: Record<Role, string> = { FREELANCER: 'Freelance', PROJECT_OWNER: 'Porteur de projet', ADMIN: 'Administrateur' }
const moderationStatusLabels: Record<ModerationStatus, string> = { OK: 'Validé', SUSPECT: 'Suspect', PENDING: 'En attente', REJETE: 'Refusé' }
const decisionLabels: Record<AnalysisDecision, string> = { OK: 'Plutôt fiable', SUSPECT: 'À vérifier', REJETE: 'Rejet conseillé' }
const criterionLabels: Record<string, string> = {
  paiement_hors_plateforme: 'Paiement ou contact hors plateforme',
  promesses_irrealistes: 'Promesses irréalistes ou garanties excessives',
  spam_incoherence: 'Spam, répétitions ou texte incohérent',
  contenu_interdit: 'Contenu illégal, haineux ou frauduleux',
  profil_trop_pauvre: 'Profil trop pauvre pour juger',
}

function formatAnalysisDate(date: string): string {
  const parsedDate = new Date(date)
  return Number.isNaN(parsedDate.getTime()) ? date : new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeStyle: 'short' }).format(parsedDate)
}

function getErrorMessage(error: unknown, context: ErrorContext): string {
  const apiMessage = error instanceof ApiError && typeof error.data === 'object' && error.data !== null && 'detail' in error.data && typeof error.data.detail === 'string'
    ? error.data.detail
    : error instanceof ApiError && typeof error.data === 'string' && error.data
      ? error.data
      : null
  if (error instanceof ApiError && error.status === 400 && typeof error.data === 'object' && error.data !== null && 'detail' in error.data && typeof error.data.detail === 'string') return error.data.detail
  if (error instanceof ApiError && error.status === 403) return 'Accès réservé aux administrateurs.'
  if (context === 'analyze') return 'L’analyse est indisponible pour le moment. Vérifiez votre connexion et réessayez.'
  if (context === 'delete') return `Suppression impossible (${error instanceof ApiError ? error.status : 'réseau'}). ${apiMessage ?? 'Veuillez réessayer.'}`
  return 'Une erreur est survenue. Veuillez réessayer.'
}

function AdminModerationPage() {
  const navigate = useNavigate()
  const [profiles, setProfiles] = useState<ModerationProfile[]>([])
  const [selectedStatus, setSelectedStatus] = useState<StatusFilter>('SUSPECT_PENDING')
  const [selectedRole, setSelectedRole] = useState<RoleFilter>('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedProfile, setSelectedProfile] = useState<ModerationProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryAction, setRetryAction] = useState<(() => void) | null>(null)
  const [profileToDelete, setProfileToDelete] = useState<ModerationProfile | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleApiError = useCallback((error: unknown, context: ErrorContext) => {
    if (error instanceof ApiError && error.status === 401) {
      clearToken()
      navigate('/login', { replace: true })
      return
    }
    setErrorMessage(getErrorMessage(error, context))
  }, [navigate])

  const loadProfiles = useCallback(async () => {
    try {
      setIsLoading(true)
      setProfiles(await apiFetch<ModerationProfile[]>('/api/admin/moderation/'))
      setErrorMessage(null)
      setRetryAction(null)
    } catch (error: unknown) {
      handleApiError(error, 'load')
      setRetryAction(() => () => void loadProfiles())
    } finally {
      setIsLoading(false)
    }
  }, [handleApiError])

  useEffect(() => {
    if (!getToken()) {
      navigate('/login', { replace: true })
      return
    }
    const timer = window.setTimeout(() => void loadProfiles(), 0)
    return () => window.clearTimeout(timer)
  }, [loadProfiles, navigate])

  useEffect(() => {
    const closePanel = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedProfile(null)
        setProfileToDelete(null)
      }
    }
    document.addEventListener('keydown', closePanel)
    return () => document.removeEventListener('keydown', closePanel)
  }, [])

  const handleViewDetails = async (profileId: number) => {
    setActionInProgress(`detail-${profileId}`)
    setErrorMessage(null)
    try {
      setSelectedProfile(await apiFetch<ModerationProfile>(`/api/admin/moderation/${profileId}/`))
    } catch (error: unknown) {
      handleApiError(error, 'detail')
    } finally {
      setActionInProgress(null)
    }
  }

  const handleAnalyze = async (profileId: number) => {
    setActionInProgress(`analyze-${profileId}`)
    setErrorMessage(null)
    setRetryAction(null)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 60000)
    try {
      const analysis = await apiFetch<ModerationAnalysis>(`/api/admin/moderation/${profileId}/analyze/`, { method: 'POST', signal: controller.signal })
      setSelectedProfile((profile) => profile?.id === profileId ? { ...profile, last_analysis: analysis } : profile)
      await loadProfiles()
    } catch (error: unknown) {
      const message = error instanceof DOMException && error.name === 'AbortError' ? 'L’analyse a dépassé 60 secondes. Vous pouvez réessayer.' : getErrorMessage(error, 'analyze')
      if (error instanceof ApiError && error.status === 401) {
        clearToken()
        navigate('/login', { replace: true })
      } else {
        setErrorMessage(message)
        setRetryAction(() => () => void handleAnalyze(profileId))
      }
    } finally {
      window.clearTimeout(timeout)
      setActionInProgress(null)
    }
  }

  const handleApprove = async (profileId: number) => {
    setActionInProgress(`approve-${profileId}`)
    setErrorMessage(null)
    try {
      await apiFetch<void>(`/api/admin/moderation/${profileId}/approve/`, { method: 'POST' })
      setProfiles((current) => current.map((profile) => profile.id === profileId ? { ...profile, moderation_status: 'OK' } : profile))
      setSelectedProfile(null)
      setSuccessMessage('Profil accepté')
    } catch (error: unknown) {
      handleApiError(error, 'approve')
    } finally {
      setActionInProgress(null)
    }
  }

  const handleDelete = async () => {
    if (!profileToDelete) return
    const profile = profileToDelete
    setActionInProgress(`delete-${profile.id}`)
    setErrorMessage(null)
    try {
      await apiFetch<void>(`/api/admin/moderation/${profile.id}/`, { method: 'DELETE' })
      setProfiles((current) => current.filter((item) => item.id !== profile.id))
      setSelectedProfile(null)
      setProfileToDelete(null)
      setSuccessMessage('Profil supprimé')
    } catch (error: unknown) {
      handleApiError(error, 'delete')
    } finally {
      setActionInProgress(null)
    }
  }

  const normalizedSearch = searchTerm.trim().toLocaleLowerCase('fr-FR')
  const visibleProfiles = profiles.filter((profile) => {
    const matchesStatus = selectedStatus === 'ALL' || (selectedStatus === 'SUSPECT_PENDING' ? profile.moderation_status === 'SUSPECT' || profile.moderation_status === 'PENDING' : profile.moderation_status === selectedStatus)
    const matchesRole = selectedRole === 'ALL' || profile.role === selectedRole
    const matchesSearch = normalizedSearch.length === 0 || profile.username.toLocaleLowerCase('fr-FR').includes(normalizedSearch)
    return matchesStatus && matchesRole && matchesSearch
  })
  const isAnalyzing = actionInProgress?.startsWith('analyze-') ?? false
  const statistics = [
    { label: 'Total', value: profiles.length, className: 'stat-total' },
    { label: 'En attente', value: profiles.filter((profile) => profile.moderation_status === 'PENDING').length, className: 'stat-pending' },
    { label: 'Suspects', value: profiles.filter((profile) => profile.moderation_status === 'SUSPECT').length, className: 'stat-suspect' },
    { label: 'Acceptés', value: profiles.filter((profile) => profile.moderation_status === 'OK').length, className: 'stat-ok' },
    { label: 'Rejetés', value: profiles.filter((profile) => profile.moderation_status === 'REJETE').length, className: 'stat-rejete' },
  ]

  if (isLoading) return <main className="admin-content-shell"><p className="loading-state">Chargement...</p></main>
  return (
    <main className="admin-content-shell">
      <div className="admin-page-intro"><div className="admin-title-icon"><ShieldCheck aria-hidden="true" size={28} /></div><div><h2>Gestion des utilisateurs</h2><p>Examinez les profils avant leur mise en relation.</p></div></div>
      {errorMessage && <div className="alert alert-error admin-message" role="alert">{errorMessage}{retryAction && <button className="btn btn-secondary btn-small" type="button" onClick={retryAction}>Réessayer</button>}</div>}
      {successMessage && <p className="alert alert-success admin-message" role="status">{successMessage}</p>}
      <section className="admin-stats" aria-label="Statistiques de modération">
        {statistics.map((stat) => <article className={`admin-stat-card ${stat.className}`} key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></article>)}
      </section>
      <section className="admin-filters card" aria-label="Filtres des utilisateurs">
        <div className="form-group admin-search-field"><label htmlFor="user-search">Rechercher par nom</label><input className="form-input" id="user-search" type="search" placeholder="Ex. marie" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} /></div>
        <div className="form-group"><label htmlFor="status-filter">Filtrer par statut</label><select className="form-input" id="status-filter" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value as StatusFilter)}><option value="SUSPECT_PENDING">Suspects et en attente</option><option value="ALL">Tous les statuts</option><option value="SUSPECT">Suspect</option><option value="PENDING">En attente</option><option value="OK">Validé</option><option value="REJETE">Refusé</option></select></div>
        <div className="form-group"><label htmlFor="role-filter">Filtrer par rôle</label><select className="form-input" id="role-filter" value={selectedRole} onChange={(event) => setSelectedRole(event.target.value as RoleFilter)}><option value="ALL">Tous les rôles</option><option value="FREELANCER">Freelance</option><option value="PROJECT_OWNER">Porteur de projet</option></select></div>
        <span className="profile-count">{visibleProfiles.length} profil(s) affiché(s)</span>
      </section>
      {visibleProfiles.length === 0 ? <div className="empty-state card"><ShieldCheck aria-hidden="true" size={30} /><p>Aucun profil à afficher.</p></div> : <div className="table-wrapper"><table className="table"><thead><tr><th>Nom d’utilisateur</th><th>E-mail</th><th>Rôle</th><th>Titre</th><th>Statut</th><th>Action</th></tr></thead><tbody>{visibleProfiles.map((profile) => <tr key={profile.id}><td>{profile.username}</td><td>{profile.email}</td><td>{roleLabels[profile.role]}</td><td>{profile.title || <span className="empty-value">Non renseigné</span>}</td><td><span className={`badge badge-${profile.moderation_status.toLowerCase()}`}>{moderationStatusLabels[profile.moderation_status]}</span></td><td><button className="btn btn-secondary btn-small" type="button" disabled={actionInProgress !== null} onClick={() => void handleViewDetails(profile.id)}><Eye aria-hidden="true" size={16} />Examiner</button></td></tr>)}</tbody></table></div>}
      {selectedProfile && <ProfileDrawer profile={selectedProfile} isAnalyzing={isAnalyzing} actionInProgress={actionInProgress} onClose={() => setSelectedProfile(null)} onAnalyze={() => void handleAnalyze(selectedProfile.id)} onApprove={() => void handleApprove(selectedProfile.id)} onDelete={() => setProfileToDelete(selectedProfile)} />}
      {profileToDelete && <DeleteModal profile={profileToDelete} isDeleting={actionInProgress === `delete-${profileToDelete.id}`} onCancel={() => setProfileToDelete(null)} onConfirm={() => void handleDelete()} />}
    </main>
  )
}

function ProfileDrawer({ profile, isAnalyzing, actionInProgress, onClose, onAnalyze, onApprove, onDelete }: { profile: ModerationProfile; isAnalyzing: boolean; actionInProgress: string | null; onClose: () => void; onAnalyze: () => void; onApprove: () => void; onDelete: () => void }) {
  const isFreelancer = profile.role === 'FREELANCER'
  return <><button className="drawer-backdrop" type="button" aria-label="Fermer le détail" onClick={onClose} /><aside className="profile-drawer" aria-label={`Détail de ${profile.username}`}><div className="detail-heading"><div><span className="admin-eyebrow">Profil utilisateur</span><h2>{profile.username}</h2></div><button className="icon-button" type="button" aria-label="Fermer le détail" onClick={onClose}><X aria-hidden="true" size={20} /></button></div><dl className="profile-details"><div><dt>E-mail</dt><dd>{profile.email || <span className="empty-value">Non renseigné</span>}</dd></div><div><dt>Rôle</dt><dd>{roleLabels[profile.role]}</dd></div><div><dt>Titre</dt><dd>{profile.title || <span className="empty-value">Non renseigné</span>}</dd></div>{isFreelancer && <><div><dt>Biographie</dt><dd>{profile.bio || <span className="empty-value">Non renseigné</span>}</dd></div><div><dt>Compétences</dt><dd>{profile.skills.length > 0 ? <div className="tag-list">{profile.skills.map((skill) => <span className="badge badge-neutral" key={skill}>{skill}</span>)}</div> : <span className="empty-value">Non renseigné</span>}</dd></div><div><dt>Tarif horaire</dt><dd>{profile.hourly_rate === null ? <span className="empty-value">Non renseigné</span> : `${profile.hourly_rate} € / heure`}</dd></div></>}</dl>{profile.moderation_status === 'PENDING' && <button className="btn btn-primary analyze-button" type="button" disabled={isAnalyzing} onClick={onAnalyze}>{isAnalyzing ? <><Loader2 className="spin" aria-hidden="true" size={18} />Analyse en cours… (peut durer jusqu’à 40 secondes)</> : 'Analyser'}</button>}{profile.last_analysis && <AnalysisPanel analysis={profile.last_analysis} />}{actionInProgress === 'analyze-error' && <p className="alert alert-error">Analyse impossible.</p>}<div className="detail-actions"><button className="btn btn-primary" type="button" disabled={actionInProgress !== null} onClick={onApprove}><Check aria-hidden="true" size={17} />Accepter</button><button className="btn btn-danger" type="button" disabled={actionInProgress !== null} onClick={onDelete}><Trash2 aria-hidden="true" size={17} />Supprimer</button></div><p className="decision-note">L’IA est une aide à la décision : la décision finale appartient à l’administrateur.</p></aside></>
}

function AnalysisPanel({ analysis }: { analysis: ModerationAnalysis }) {
  return <section className={`analysis-panel analysis-${analysis.decision.toLowerCase()}`}><h3 title={`Analysé le ${formatAnalysisDate(analysis.analyzed_at)}`}>Résultat de l’analyse</h3>{analysis.simulated && <p className="simulation-banner">Analyse simulée (mode démonstration) : ce résultat vient d&apos;un simulateur, pas d&apos;un vrai modèle d&apos;IA.</p>}<div className="analysis-verdict"><span className={`badge badge-${analysis.decision.toLowerCase()}`}>{decisionLabels[analysis.decision]}</span><span className="confidence-label" title="Niveau de certitude de l’IA dans son verdict, pas une probabilité de fraude">Confiance de l’IA : {analysis.confidence_percent === null ? '—' : `${analysis.confidence_percent} %`}</span></div>{analysis.confidence_percent !== null && <progress max="100" value={analysis.confidence_percent} aria-label={`Confiance de l’IA : ${analysis.confidence_percent} %`} />}{analysis.error && <p className="alert alert-error">Analyse IA indisponible : vérifiez le profil manuellement</p>}<h4>Pourquoi ce résultat ?</h4><p>{analysis.reason || <span className="empty-value">Non renseigné</span>}</p>{analysis.criteria.length > 0 && <><h4>Critères examinés</h4><ul className="criteria-list">{analysis.criteria.map((criterion) => <CriterionRow criterion={criterion} key={criterion.id} />)}</ul></>}</section>
}

function CriterionRow({ criterion }: { criterion: ModerationCriterion }) {
  return <li className={criterion.probleme ? 'criterion-problem' : 'criterion-ok'}>{criterion.probleme ? <AlertTriangle aria-hidden="true" size={18} /> : <CheckCircle2 aria-hidden="true" size={18} />}<span><strong>{criterionLabels[criterion.id] ?? criterion.id}</strong><small>{criterion.probleme ? `détecté${criterion.commentaire ? ` — ${criterion.commentaire}` : ''}` : 'non détecté'}</small></span></li>
}

function DeleteModal({ profile, isDeleting, onCancel, onConfirm }: { profile: ModerationProfile; isDeleting: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <div className="modal-backdrop" role="presentation"><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-title"><h2 id="delete-title">Supprimer le profil ?</h2><p>Supprimer définitivement le compte de <strong>{profile.username}</strong> ? Cette action est irréversible.</p><div className="detail-actions"><button className="btn btn-secondary" type="button" disabled={isDeleting} onClick={onCancel}>Annuler</button><button className="btn btn-danger" type="button" disabled={isDeleting} onClick={onConfirm}>{isDeleting ? <><Loader2 className="spin" aria-hidden="true" size={17} />Suppression...</> : 'Supprimer définitivement'}</button></div></section></div>
}

export default AdminModerationPage
