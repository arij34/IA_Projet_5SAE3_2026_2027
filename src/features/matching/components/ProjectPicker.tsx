import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderPlus, Users2, UsersRound } from 'lucide-react'
import { listProjects } from '../../../api/projects'
import type { Project } from '../../../types/project'

interface Props {
  title: string
}

/**
 * Sélecteur de projet du porteur connecté.
 *
 * Utilise l'API projets existante en lecture seule ; aucune donnée n'est
 * modifiée dans le module projects. Chaque carte propose les deux actions du
 * matching et transmet l'identifiant réel du projet affiché.
 */
function ProjectPicker({ title }: Props) {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let mounted = true
    void listProjects()
      .then((items) => {
        if (mounted) setProjects(items)
      })
      .catch(() => {
        if (mounted) setFailed(true)
      })
    return () => {
      mounted = false
    }
  }, [])

  if (failed) {
    return (
      <div className="matching-state is-error" role="alert">
        <p>Vos projets n'ont pas pu être chargés.</p>
        <Link className="btn btn-secondary btn-small" to="/gestion-projets">
          Ouvrir la gestion de projet
        </Link>
      </div>
    )
  }

  if (projects === null) {
    return (
      <p className="matching-state" role="status" aria-busy="true">
        Chargement de vos projets...
      </p>
    )
  }

  const analyzed = projects.filter(
    (project) => project.status === 'ANALYZED' || project.status === 'PUBLISHED',
  )

  if (analyzed.length === 0) {
    return (
      <div className="matching-state">
        <p>
          {projects.length === 0
            ? "Vous n'avez pas encore de projet. Créez-en un, puis lancez son analyse pour obtenir des recommandations."
            : "Aucun de vos projets n'est encore analysé. Lancez l'analyse IA d'un projet pour obtenir des recommandations."}
        </p>
        <div className="matching-actions is-centered">
          <Link className="btn btn-primary btn-small" to="/projects/new">
            <FolderPlus aria-hidden="true" size={15} />
            Créer un projet
          </Link>
          <Link className="btn btn-secondary btn-small" to="/gestion-projets">
            Ouvrir la gestion de projet
          </Link>
        </div>
      </div>
    )
  }

  return (
    <section aria-labelledby="matching-project-picker">
      <h2 className="matching-subtitle" id="matching-project-picker">
        {title}
      </h2>
      <ul className="matching-list">
        {analyzed.map((project) => (
          <li className="card" key={project.id}>
            <div className="match-card-head">
              <div className="match-identity">
                <h3>{project.name}</h3>
                <p>{project.description.slice(0, 180)}</p>
                <div className="match-badges">
                  <span className="match-badge">
                    {project.status === 'PUBLISHED' ? 'Publié' : 'Analysé'}
                  </span>
                  <span className="match-badge">
                    Échéance : {project.deadline}
                  </span>
                </div>
              </div>
            </div>
            <div className="match-footer">
              <span className="breakdown-detail">
                Choisissez une action pour ce projet.
              </span>
              <div className="matching-actions">
                <Link
                  className="btn btn-primary btn-small"
                  to={`/matching/projects/${project.id}/freelancers`}
                  aria-label={`Voir les freelances recommandés pour ${project.name}`}
                >
                  <Users2 aria-hidden="true" size={15} />
                  Voir les freelances recommandés
                </Link>
                <Link
                  className="btn btn-secondary btn-small"
                  to={`/matching/projects/${project.id}/team`}
                  aria-label={`Composer une équipe pour ${project.name}`}
                >
                  <UsersRound aria-hidden="true" size={15} />
                  Composer une équipe
                </Link>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default ProjectPicker
