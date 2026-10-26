import { getToken } from '../auth/tokenStorage'

export type ApiFetchOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly data: unknown

  constructor(status: number, data: unknown) {
    super(`La requête a échoué avec le statut ${status}.`)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export interface ProfileAnalysisData {
  title: string
  bio: string
  skills: string[] | string
  hourly_rate?: number | string | null
}

export interface ProfilePayload {
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
}

export type ProfileAnalysisRequest = ProfilePayload

export interface ProfileAnalysisResponse {
  score: number
  points_forts: string[]
  points_faibles: string[]
  suggestions: string[]
  source: 'model' | 'fallback'
}

export class ApiTimeoutError extends Error {
  constructor() {
    super('L’analyse du profil a dépassé le délai autorisé.')
    this.name = 'ApiTimeoutError'
  }
}

export function normalizeProfilePayload(profile: ProfileAnalysisData): ProfilePayload {
  const payload: ProfilePayload = {
    title: String(profile.title || '').trim(),
    bio: String(profile.bio || '').trim(),
    skills: Array.isArray(profile.skills)
      ? profile.skills
          .map((skill) => String(skill).trim())
          .filter(Boolean)
      : String(profile.skills || '')
          .split(',')
          .map((skill) => skill.trim())
          .filter(Boolean),
    hourly_rate:
      profile.hourly_rate === '' ||
      profile.hourly_rate === null ||
      profile.hourly_rate === undefined
        ? null
        : Number(profile.hourly_rate),
  }

  if (!payload.title) {
    throw new Error('Le titre est obligatoire.')
  }
  if (!payload.bio) {
    throw new Error('La bio est obligatoire.')
  }
  if (!Number.isFinite(payload.hourly_rate) && payload.hourly_rate !== null) {
    throw new Error('Le tarif horaire doit être un nombre valide.')
  }

  return payload
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { body, ...requestOptions } = options
  const headers = new Headers(requestOptions.headers)
  if (!(body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const isPublicAuthRequest =
    path === '/api/auth/login/' || path === '/api/auth/register/'
  const token = isPublicAuthRequest ? null : getToken()
  if (token) {
    headers.set('Authorization', `Token ${token}`)
  }

  const response = await fetch(path, {
    ...requestOptions,
    headers,
    body:
      body !== undefined && typeof body !== 'string'
        ? body instanceof FormData ? body : JSON.stringify(body)
        : body,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const responseText = await response.text()
  const contentType = response.headers.get('content-type')
  const data =
    responseText.length > 0 && contentType?.includes('application/json')
      ? JSON.parse(responseText) as unknown
      : responseText

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }

  return data as T
}

export async function analyzeProfile(
  profile: ProfileAnalysisData,
): Promise<ProfileAnalysisResponse> {
  const token = getToken()
  const payload = normalizeProfilePayload(profile)

  console.log('Payload analyse profil :', payload)
  if (!token) {
    throw new ApiError(401, { detail: 'Jeton manquant.' })
  }

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), 100_000)

  try {
    const result = await apiFetch<ProfileAnalysisResponse>('/api/ai/profile-analysis/', {
      method: 'POST',
      body: payload,
      signal: controller.signal,
    })
    console.log('Réponse analyse profil :', result)
    return result
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      console.error('Réponse analyse profil :', error.data)
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiTimeoutError()
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export function apiFetchFormData<T>(
  path: string,
  formData: FormData,
  method: 'PATCH' | 'POST' = 'PATCH',
): Promise<T> {
  return apiFetch<T>(path, {
    method,
    body: formData,
  })
}

export function changePassword(value: {
  oldPassword: string
  newPassword: string
}): Promise<void> {
  // TODO: brancher l’endpoint de changement de mot de passe exposé par le back.
  void value
  return Promise.reject(new Error('Le changement de mot de passe sera disponible lorsque le back exposera son endpoint.'))
}
