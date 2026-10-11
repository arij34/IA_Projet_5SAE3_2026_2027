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

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { body, ...requestOptions } = options
  const headers = new Headers(requestOptions.headers)
  headers.set('Content-Type', 'application/json')

  const token = getToken()
  if (token) {
    headers.set('Authorization', `Token ${token}`)
  }

  const response = await fetch(path, {
    ...requestOptions,
    headers,
    body:
      body !== undefined && typeof body !== 'string'
        ? JSON.stringify(body)
        : body,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type')
  const data = contentType?.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }

  return data as T
}
