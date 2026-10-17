import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/useAuth'
import { getToken } from './auth/tokenStorage'
import Layout from './components/Layout'
import AdminModerationPage from './pages/AdminModerationPage'
import AdminDashboardLayout from './pages/AdminDashboardLayout'
import AssistantPage from './pages/AssistantPage'
import ChallengesPage from './pages/ChallengesPage'
import ChallengeAttemptPage from './pages/ChallengeAttemptPage'
import ChallengeResultsPage from './pages/ChallengeResultsPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NewProjectPage from './pages/NewProjectPage'
import MyProjectsPage from './pages/MyProjectsPage'
import ProfilePage from './pages/ProfilePage'
import PublishedProjectsPage from './pages/PublishedProjectsPage'
import RegisterPage from './pages/RegisterPage'

function ProjectOwnerRoute() {
  const location = useLocation()
  const { user } = useAuth()

  if (!getToken()) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (user === null) return <p className="loading-state">Chargement...</p>
  if (user?.role !== 'PROJECT_OWNER') return <Navigate to="/" replace />
  return <Outlet />
}

function FreelancerRoute() {
  const location = useLocation()
  const { user, isLoading } = useAuth()

  if (!getToken()) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (isLoading) return <p className="loading-state" role="status">Chargement de votre profil...</p>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (user.role !== 'FREELANCER' || user.moderation_status !== 'OK') {
    return <Navigate to="/profile" replace />
  }
  return <Outlet />
}

function App() {
  return (
    <Routes>
      <Route path="/admin" element={<AdminDashboardLayout />}>
        <Route index element={<Navigate to="users" replace />} />
        <Route path="users" element={<AdminModerationPage />} />
      </Route>
      <Route path="/admin/moderation" element={<Navigate to="/admin/users" replace />} />
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<FreelancerRoute />}>
          <Route path="/challenges" element={<ChallengesPage />} />
          <Route path="/challenges/attempts/:attemptId/results" element={<ChallengeResultsPage />} />
          <Route path="/challenges/attempts/:attemptId" element={<ChallengeAttemptPage />} />
        </Route>
        <Route element={<ProjectOwnerRoute />}>
          <Route path="/projects/new" element={<NewProjectPage />} />
          <Route path="/projects/:projectId/edit" element={<NewProjectPage />} />
          <Route path="/projects" element={<MyProjectsPage />} />
          <Route path="/gestion-projets" element={<MyProjectsPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
        </Route>
        <Route path="/projects/published" element={<PublishedProjectsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  )
}

export default App
