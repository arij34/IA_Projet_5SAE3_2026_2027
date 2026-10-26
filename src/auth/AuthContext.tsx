import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api/client'
import { getToken } from './tokenStorage'
import type { User } from '../types'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(() => Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return
    let isMounted = true
    void apiFetch<User>('/api/users/me/')
      .then((profile) => { if (isMounted) setUser(profile) })
      .catch(() => { if (isMounted) setUser(null) })
      .finally(() => { if (isMounted) setIsLoading(false) })
    return () => { isMounted = false }
  }, [])

  const value = useMemo(() => ({ user, setUser, isLoading }), [user, isLoading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
