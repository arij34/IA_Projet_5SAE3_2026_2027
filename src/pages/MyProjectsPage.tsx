import { useEffect, useState } from 'react'
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { deleteProject, listProjects } from '../api/projects'
import type { Project, ProjectStatus } from '../types/project'

type LocationState = {
  successMessage?: string
}

const statusLabels: Record<ProjectStatus, string> = {
  DRAFT: 'Brouillon',
  ANALYZED: 'Analysé',
  PUBLISHED: 'Publié',
  DECLINED: 'Refusé',
}

const statusClasses: Record<ProjectStatus, string> = {
  DRAFT: 'badge-neutral',
  ANALYZED: 'badge-suspect',
  PUBLISHED: 'badge-ok',
  DECLINED: 'badge-rejete',
}

function formatDeadline(deadline: string): string {
  return new Date(`${deadline}T00:00:00`).toLocaleDateString('fr-FR')
}

function MyProjectsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage] = useState<string | null>(
    (location.state as LocationState | null)?.successMessage ?? null,
  )

  const loadProjects = async (isMounted: () => boolean = () => true) => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listProjects()
      if (!isMounted()) return
      setProjects(response)
    } catch (error: unknown) {
      if (!isMounted()) return
      setErrorMessage(error instanceof Error ? error.message : 'Impossible de charger vos projets.')
    } finally {
      if (isMounted()) setIsLoading(false)
    }
  }

  useEffect(() => {
    let isMounted = true
    const timeoutId = window.setTimeout(() => {
      if (isMounted) void loadProjects(() => isMounted)
    }, 0)

    return () => {
      isMounted = false
      window.clearTimeout(timeoutId)
    }
  }, [])

  useEffect(() => {
    if (successMessage) {
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [successMessage])

  const handleDelete = async (project: Project) => {
    if (!window.confirm(`Supprimer le projet « ${project.name} » ?`)) return
    setBusyId(project.id)
    setErrorMessage(null)
    try {
      await deleteProject(project.id)
      setProjects((current) => current.filter((item) => item.id !== project.id))
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : 'Impossible de supprimer le projet.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <main className="page-shell">
      <section className="card page-card">
        <div className="profile-heading">
          <div>
            <h1>Gestion de projet</h1>
            <p>Gérez vos projets et suivez leur état de publication.</p>
          </div>
          <button className="btn btn-primary" type="button" onClick={() => navigate('/projects/new')}>
            <Plus aria-hidden="true" size={17} /> Créer un projet
          </button>
        </div>

        {successMessage && <p className="alert alert-success" role="status">{successMessage}</p>}
        {errorMessage && <p className="alert alert-error" role="alert">{errorMessage}</p>}
        {isLoading && <p className="loading-state"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement des projets...</p>}
        {!isLoading && projects.length === 0 && (
          <div className="empty-state">
            <p>Vous n’avez encore aucun projet.</p>
            <button className="btn btn-primary" type="button" onClick={() => navigate('/projects/new')}>Créer un projet</button>
          </div>
        )}

        {!isLoading && projects.length > 0 && (
          <div className="project-list">
            {projects.map((project) => {
              const isBusy = busyId === project.id
              const isPublished = project.status === 'PUBLISHED'
              return (
                <article className="card project-list-item" key={project.id}>
                  <div className="profile-heading">
                    <div>
                      <h2>{project.name}</h2>
                      <p>Date limite : {formatDeadline(project.deadline)}</p>
                      <p>Montant estimé : {project.estimated_amount} €</p>
                    </div>
                    <span className={`badge ${statusClasses[project.status]}`}>{statusLabels[project.status]}</span>
                  </div>
                  <div className="form-row">
                    <button
                      className="btn btn-secondary"
                      type="button"
                      aria-label={`Modifier le projet ${project.name}`}
                      title={isPublished ? 'Un projet publié ne peut plus être modifié' : 'Modifier le projet'}
                      onClick={() => navigate(`/projects/${project.id}/edit`)}
                      disabled={isPublished || isBusy}
                    >
                      <Pencil aria-hidden="true" size={16} /> Modifier
                    </button>
                    <button
                      className="btn btn-danger"
                      type="button"
                      aria-label={`Supprimer le projet ${project.name}`}
                      title="Supprimer le projet"
                      onClick={() => void handleDelete(project)}
                      disabled={isBusy}
                    >
                      <Trash2 aria-hidden="true" size={16} /> Supprimer
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </main>
  )
}

export default MyProjectsPage
