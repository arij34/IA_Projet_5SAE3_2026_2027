import { useEffect, useState } from 'react'
import { getProject } from '../../../api/projects'

/**
 * Récupère le nom d'un projet pour afficher le contexte en en-tête.
 *
 * Lecture seule sur l'API projets existante. Un échec reste silencieux :
 * la page reste utilisable sans le nom.
 */
export function useProjectName(projectId: number): string | null {
  const key = String(projectId)
  const [resolved, setResolved] = useState<{ key: string; name: string | null }>(
    { key: '', name: null },
  )

  useEffect(() => {
    if (!Number.isFinite(projectId) || projectId <= 0) return
    let mounted = true
    void getProject(projectId)
      .then((project) => {
        if (mounted) setResolved({ key, name: project.name })
      })
      .catch(() => {
        if (mounted) setResolved({ key, name: null })
      })
    return () => {
      mounted = false
    }
  }, [projectId, key])

  return resolved.key === key ? resolved.name : null
}
