import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api/client'
import { getToken } from './tokenStorage'
import type { User } from '../types'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    if (!getToken()) return
    void apiFetch<User>('/api/users/me/')
      .then(setUser)
      .catch(() => setUser(null))
  }, [])

  const value = useMemo(() => ({ user, setUser }), [user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
