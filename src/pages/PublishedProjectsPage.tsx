import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { ApiError } from '../api/projects'
import { apiFetch } from '../api/client'
import type { Paginated, PublicProject, Project } from '../types/project'

type PublicProjectDetails = PublicProject & {
  date_limite?: string
  deadline?: string
  complexite?: string
  specialites?: string[]
  duree_semaines?: number
}

function details(project: PublicProject): PublicProjectDetails {
  return project as PublicProjectDetails
}

function formatDate(project: PublicProject): string {
  const value = details(project).date_limite ?? details(project).deadline
  return value ? new Date(value).toLocaleDateString('fr-FR') : 'Date non renseignée'
}

function formatAmount(project: Project): string {
  return `${project.budget_min} – ${project.budget_max} ${project.devise}`
}

function PublishedProjectsPage() {
  const [projects, setProjects] = useState<PublicProject[]>([])
  const [page, setPage] = useState(1)
  const [next, setNext] = useState<string | null>(null)
  const [previous, setPrevious] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    setIsLoading(true)
    setErrorMessage(null)
    void apiFetch<Paginated<PublicProject>>(`/api/projects/published/?page=${page}`)
      .then((response) => {
        if (!isMounted) return
        setProjects(response.results)
        setNext(response.next)
        setPrevious(response.previous)
      })
      .catch((error: unknown) => {
        if (isMounted) setErrorMessage(error instanceof ApiError ? error.message : 'Impossible de charger les projets publiés.')
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => { isMounted = false }
  }, [page])

  return (
    <main className="page-shell">
      <section className="card page-card">
        <div className="auth-heading">
          <h1>Projets publiés</h1>
          <p>Découvrez les projets ouverts aux collaborations.</p>
        </div>
        {errorMessage && <p className="alert alert-error" role="alert">{errorMessage}</p>}
        {isLoading && <p className="loading-state"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement des projets...</p>}
        {!isLoading && projects.length === 0 && <p className="empty-state">Aucun projet publié pour le moment.</p>}
        <div className="project-grid">
          {projects.map((project) => {
            const item = details(project)
            return (
              <article className="card project-card" key={project.id}>
                <h2>{project.title}</h2>
                <p>{project.description.length > 180 ? `${project.description.slice(0, 180)}…` : project.description}</p>
                <dl>
                  <dt>Date limite</dt><dd>{formatDate(project)}</dd>
                  <dt>Montant</dt><dd>{formatAmount(project)}</dd>
                  <dt>Spécialités</dt><dd>{item.specialites?.join(', ') || 'Non renseignées'}</dd>
                  <dt>Durée</dt><dd>{item.duree_semaines ? `${item.duree_semaines} semaines` : 'Non renseignée'}</dd>
                  <dt>Complexité</dt><dd>{item.complexite || 'Non renseignée'}</dd>
                </dl>
              </article>
            )
          })}
        </div>
        {!isLoading && projects.length > 0 && (
          <nav className="form-row" aria-label="Pagination">
            <button className="btn btn-secondary" type="button" disabled={!previous} onClick={() => setPage((current) => Math.max(1, current - 1))}>Précédent</button>
            <span>Page {page}</span>
            <button className="btn btn-secondary" type="button" disabled={!next} onClick={() => setPage((current) => current + 1)}>Suivant</button>
          </nav>
        )}
      </section>
    </main>
  )
}

export default PublishedProjectsPage
