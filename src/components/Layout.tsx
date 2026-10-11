import { useState } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { clearToken, getToken } from '../auth/tokenStorage'

function Layout() {
  const navigate = useNavigate()
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getToken()))

  const handleLogout = () => {
    clearToken()
    setIsAuthenticated(false)
    navigate('/login')
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="container site-header-inner">
          <Link className="brand" to="/">
            Freelancy
          </Link>
          <nav className="site-nav" aria-label="Navigation principale">
            <Link to="/">Accueil</Link>
            {isAuthenticated ? (
              <>
                <Link to="/profile">Mon profil</Link>
                <button type="button" onClick={handleLogout}>
                  Se déconnecter
                </button>
              </>
            ) : (
              <>
                <Link to="/login">Connexion</Link>
                <Link to="/register">Inscription</Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="site-main">
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="container">
          Freelancy — Des collaborations de confiance.
        </div>
      </footer>
    </div>
  )
}

export default Layout
