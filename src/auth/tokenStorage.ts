const tokenKey = 'freelancy_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(tokenKey) ?? localStorage.getItem('token')
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(tokenKey, token)
  } catch {
    // Le stockage peut être indisponible dans certains environnements.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(tokenKey)
  } catch {
    // Le stockage peut être indisponible dans certains environnements.
  }
}
