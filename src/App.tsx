import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import AdminModerationPage from './pages/AdminModerationPage'
import AdminDashboardLayout from './pages/AdminDashboardLayout'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'

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
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  )
}

export default App
