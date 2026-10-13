import { ApiError as ClientApiError, apiFetch } from './client'
import type {
  AnalysisResponse,
  ChatbotResponse,
  Paginated,
  Project,
  ProjectInput,
  ProjectStatus,
  PublicProject,
} from '../types/project'

export const MAX_CHATBOT_QUESTION_CHARS = 1000

/**
 * Erreur HTTP exposée par les appels projets, sans inclure de données sensibles.
 */
export class ApiError extends Error {
  readonly code: number
  readonly data: unknown

  constructor(code: number, data: unknown) {
    super(getErrorMessage(code, data))
    this.name = 'ApiError'
    this.code = code
    this.data = data
  }
}

function getErrorMessage(code: number, data: unknown): string {
  if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
    return data.detail
  }
  switch (code) {
    case 404:
      return 'Le projet demandé est introuvable.'
    case 409:
      return 'Cette action ne peut pas être effectuée dans l’état actuel du projet.'
    case 429:
      return 'Trop de demandes ont été effectuées. Veuillez réessayer plus tard.'
    default:
      return `La requête du projet a échoué (code ${code}).`
  }
}

async function projectRequest<T>(
  path: string,
  options: {
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
    body?: ProjectInput | Partial<ProjectInput>
  },
): Promise<T> {
  try {
    return await apiFetch<T>(path, options)
  } catch (error: unknown) {
    if (error instanceof ClientApiError) {
      throw new ApiError(error.status, error.data)
    }
    throw error
  }
}

export function createProject(input: ProjectInput): Promise<Project> {
  return projectRequest<Project>('/api/projects/', {
    method: 'POST',
    body: input,
  })
}

export async function listProjects(status?: ProjectStatus): Promise<Project[]> {
  const query = status
    ? `?${new URLSearchParams({ status }).toString()}`
    : ''
  const response = await projectRequest<Project[] | Paginated<Project>>(`/api/projects/${query}`, {
    method: 'GET',
  })
  return Array.isArray(response) ? response : response.results
}

export function getProject(id: number): Promise<Project> {
  return projectRequest<Project>(`/api/projects/${id}/`, {
    method: 'GET',
  })
}

export function updateProject(
  id: number,
  input: Partial<ProjectInput>,
): Promise<Project> {
  return projectRequest<Project>(`/api/projects/${id}/`, {
    method: 'PATCH',
    body: input,
  })
}

export function deleteProject(id: number): Promise<void> {
  return projectRequest<void>(`/api/projects/${id}/`, {
    method: 'DELETE',
  })
}

export function analyzeProject(id: number): Promise<AnalysisResponse> {
  return projectRequest<AnalysisResponse>(`/api/projects/${id}/analyze/`, {
    method: 'POST',
  })
}

export async function askChatbot(question: string): Promise<ChatbotResponse> {
  try {
    return await apiFetch<ChatbotResponse>('/api/projects/chatbot/', {
      method: 'POST',
      body: { question },
    })
  } catch (error: unknown) {
    if (error instanceof ClientApiError) {
      throw new ApiError(error.status, error.data)
    }
    throw error
  }
}

export function publishProject(id: number): Promise<Project> {
  return projectRequest<Project>(`/api/projects/${id}/publish/`, {
    method: 'POST',
  })
}

export function declineProject(id: number): Promise<Project> {
  return projectRequest<Project>(`/api/projects/${id}/decline/`, {
    method: 'POST',
  })
}

export function listPublishedProjects(): Promise<Paginated<PublicProject>> {
  return projectRequest<Paginated<PublicProject>>('/api/projects/published/', {
    method: 'GET',
  })
}
