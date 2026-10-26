import { Menu, Users, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, apiFetch } from '../api/client'
import { clearToken, getToken } from '../auth/tokenStorage'
import { useAuth } from '../auth/useAuth'
import type { User } from '../types'

type AdminProfile = User & { first_name?: string; last_name?: string }

const adminMenuItems = [{ label: 'Utilisateurs', to: '/admin/users', icon: Users }] as const

function AdminDashboardLayout() {
  const navigate = useNavigate()
  const { user: authenticatedUser, setUser: setAuthenticatedUser } = useAuth()
  const location = useLocation()
  const [admin, setAdmin] = useState<AdminProfile | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    const saved = window.localStorage.getItem('freelancy_admin_sidebar')
    return saved === null ? window.innerWidth > 800 : saved === 'open'
  })
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    window.localStorage.setItem('freelancy_admin_sidebar', isSidebarOpen ? 'open' : 'closed')
  }, [isSidebarOpen])

  useEffect(() => {
    let isMounted = true
    const loadAdmin = async () => {
      if (!getToken()) {
        navigate('/login', { replace: true })
        return
      }
      try {
        const profile = await apiFetch<AdminProfile>('/api/users/me/')
        if (profile.role !== 'ADMIN') {
          if (isMounted) navigate('/profile', { replace: true })
          return
        }
        if (isMounted) {
          setAdmin(profile)
          setAuthenticatedUser(profile)
        }
      } catch (error: unknown) {
        if (error instanceof ApiError && error.status === 401) {
          clearToken()
          navigate('/login', { replace: true })
        } else if (isMounted && error instanceof ApiError && error.status === 403) {
          setErrorMessage('Accès réservé aux administrateurs.')
        } else if (isMounted) {
          setErrorMessage('Impossible de charger votre session administrateur.')
        }
      }
    }
    void loadAdmin()
    return () => { isMounted = false }
  }, [navigate, setAuthenticatedUser])

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsSidebarOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [])

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  if (errorMessage) return <main className="admin-error-page"><p className="alert alert-error" role="alert">{errorMessage}</p></main>
  if (!admin) return <main className="admin-error-page"><p className="loading-state">Chargement...</p></main>

  const displayName = authenticatedUser?.username || admin.username || `${admin.first_name ?? ''} ${admin.last_name ?? ''}`.trim()
  const initial = displayName.charAt(0).toUpperCase() || 'A'
  const sectionTitle = adminMenuItems.find((item) => location.pathname.startsWith(item.to))?.label ?? 'Administration'

  return (
    <div className={`admin-dashboard${isSidebarOpen ? ' sidebar-open' : ' sidebar-closed'}`}>
      <aside className="admin-sidebar">
        <div className="admin-brand"><span className="admin-brand-mark">F</span><span>Freelancy</span></div>
        <nav aria-label="Navigation d’administration">
          {adminMenuItems.map(({ label, to, icon: Icon }) => (
            <NavLink key={to} className={({ isActive }) => `admin-nav-link${isActive ? ' active' : ''}`} to={to} onClick={() => { if (window.innerWidth <= 800) setIsSidebarOpen(false) }}>
              <Icon aria-hidden="true" size={19} />{label}
            </NavLink>
          ))}
        </nav>
      </aside>
      {isSidebarOpen && <button className="admin-sidebar-overlay" type="button" aria-label="Fermer le menu" onClick={() => setIsSidebarOpen(false)} />}
      <div className="admin-dashboard-main">
        <header className="admin-dashboard-header">
          <button className="admin-menu-toggle" type="button" aria-label={isSidebarOpen ? 'Fermer le menu' : 'Ouvrir le menu'} aria-expanded={isSidebarOpen} onClick={() => setIsSidebarOpen((open) => !open)}>
            {isSidebarOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
          <h1>{sectionTitle}</h1>
          <div className="admin-user"><span className="admin-user-initial">{initial}</span><strong>{displayName}</strong><Link className="btn btn-secondary btn-small" to="/profile">Mon profil</Link><button className="btn btn-secondary btn-small" type="button" onClick={logout}>Se déconnecter</button></div>
        </header>
        <Outlet />
      </div>
    </div>
  )
}

export default AdminDashboardLayout
