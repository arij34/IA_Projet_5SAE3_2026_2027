import { BriefcaseBusiness, Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { clearToken, getToken } from '../auth/tokenStorage'

function Layout() {
  const navigate = useNavigate()
  const { user, setUser } = useAuth()
  const isAuthenticated = Boolean(getToken())
  const isApprovedFreelancer = isAuthenticated && user?.role === 'FREELANCER' && user?.moderation_status === 'OK'
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [hasScrolled, setHasScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setHasScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false)
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const closeMenu = () => setIsMenuOpen(false)

  const handleLogout = () => {
    clearToken()
    setUser(null)
    closeMenu()
    navigate('/login')
  }

  const navClassName = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'nav-link active' : 'nav-link'

  return (
    <div className="site-shell">
      <header className={`site-header${hasScrolled ? ' is-scrolled' : ''}`}>
        <div className="container site-header-inner">
          <Link className="brand" to="/" onClick={closeMenu}>
            <BriefcaseBusiness aria-hidden="true" size={22} />
            <span>Freelancy</span>
          </Link>
          <button
            className="menu-toggle"
            type="button"
            aria-label={isMenuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
            aria-expanded={isMenuOpen}
            onClick={() => setIsMenuOpen((open) => !open)}
          >
            {isMenuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
          <nav
            className={`site-nav${isMenuOpen ? ' is-open' : ''}`}
            aria-label="Navigation principale"
          >
            <NavLink className={navClassName} to="/" end onClick={closeMenu}>
              Accueil
            </NavLink>
            {isAuthenticated ? (
              <>
                {isApprovedFreelancer && (
                  <NavLink className={navClassName} to="/challenges" onClick={closeMenu}>
                    Challenges
                  </NavLink>
                )}
                {isApprovedFreelancer && (
                  <NavLink className={navClassName} to="/matching/projets-recommandes" onClick={closeMenu}>
                    Projets recommandés
                  </NavLink>
                )}
                <NavLink className={navClassName} to="/profile" onClick={closeMenu}>
                  Mon profil
                </NavLink>
                {user?.role === 'PROJECT_OWNER' && (
                  <>
                    <NavLink className={navClassName} to="/planning" onClick={closeMenu}>
                      Planning
                    </NavLink>
                    <NavLink className={navClassName} to="/gestion-projets" onClick={closeMenu}>
                      Gestion de projet
                    </NavLink>
                    <NavLink className={navClassName} to="/assistant" onClick={closeMenu}>
                      Assistant
                    </NavLink>
                    <NavLink className={navClassName} to="/matching/projects" onClick={closeMenu}>
                      Recommandations
                    </NavLink>
                    <NavLink className={navClassName} to="/matching/equipes" onClick={closeMenu}>
                      Composer une équipe
                    </NavLink>
                  </>
                )}
                <button type="button" onClick={handleLogout}>
                  Se déconnecter
                </button>
              </>
            ) : (
              <>
                <NavLink className="nav-link nav-login" to="/login" onClick={closeMenu}>
                  Se connecter
                </NavLink>
                <NavLink className="btn btn-primary nav-register" to="/register" onClick={closeMenu}>
                  S'inscrire
                </NavLink>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="site-main">
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="container footer-grid">
          <div className="footer-brand">
            <Link className="brand footer-logo" to="/">
              <BriefcaseBusiness aria-hidden="true" size={22} />
              <span>Freelancy</span>
            </Link>
            <p>La plateforme de confiance pour créer des collaborations qui comptent.</p>
            <div className="social-links" aria-label="Réseaux sociaux">
              <button type="button" disabled aria-label="Réseau Freelancy"><BriefcaseBusiness aria-hidden="true" size={18} /></button>
              <button type="button" disabled aria-label="Contact Freelancy"><BriefcaseBusiness aria-hidden="true" size={18} /></button>
              <button type="button" disabled aria-label="Communauté Freelancy"><BriefcaseBusiness aria-hidden="true" size={18} /></button>
            </div>
          </div>
          <div>
            <h2>Plateforme</h2>
            <Link to="/">Accueil</Link>
            <Link to="/register">Inscription</Link>
            <Link to="/login">Connexion</Link>
          </div>
          <div>
            <h2>Ressources</h2>
            <span>Guides et conseils</span>
            {isApprovedFreelancer && <Link to="/challenges">Challenges</Link>}
            <span>Blog</span>
          </div>
          <div>
            <h2>Contact</h2>
            <span>Une question ?</span>
            <span>Notre équipe vous répond.</span>
          </div>
        </div>
        <div className="container footer-bottom">
          <span>© {new Date().getFullYear()} Freelancy. Tous droits réservés.</span>
        </div>
      </footer>
    </div>
  )
}

export default Layout
