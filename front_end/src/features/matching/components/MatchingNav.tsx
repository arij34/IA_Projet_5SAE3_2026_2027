import { ArrowLeft, FolderOpen, Users2, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'

interface Props {
  /** Page courante, pour ne pas proposer un lien vers elle-même. */
  current: 'freelancers' | 'team'
  /** Identifiant réel du projet affiché, jamais une valeur codée en dur. */
  projectId: number
  /** Nom du projet lorsqu'il a pu être chargé. */
  projectName: string | null
}

/**
 * Fil de navigation du matching : retour aux projets et passage d'une vue
 * à l'autre en conservant le projet courant.
 */
function MatchingNav({ current, projectId, projectName }: Props) {
  return (
    <nav className="matching-breadcrumb" aria-label="Navigation du matching">
      <Link className="btn btn-secondary btn-small" to="/matching/projects">
        <ArrowLeft aria-hidden="true" size={15} />
        Retour à mes projets
      </Link>

      {current === 'team' ? (
        <Link
          className="btn btn-secondary btn-small"
          to={`/matching/projects/${projectId}/freelancers`}
        >
          <Users2 aria-hidden="true" size={15} />
          Retour aux freelances recommandés
        </Link>
      ) : (
        <Link
          className="btn btn-secondary btn-small"
          to={`/matching/projects/${projectId}/team`}
        >
          <UsersRound aria-hidden="true" size={15} />
          Composer une équipe
        </Link>
      )}

      <span className="matching-context">
        <FolderOpen aria-hidden="true" size={15} />
        {projectName ? (
          <>
            Projet : <strong>{projectName}</strong>
          </>
        ) : (
          <>Projet numéro {projectId}</>
        )}
      </span>
    </nav>
  )
}

export default MatchingNav
