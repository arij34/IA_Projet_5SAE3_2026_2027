import { useContext } from 'react'
import { AuthContext } from './context'

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth doit être utilisé dans AuthProvider.')
  }
  return context
}
