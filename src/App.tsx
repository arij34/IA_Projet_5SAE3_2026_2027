import { Navigate, Route, Routes } from 'react-router-dom'
import AdminModerationPage from './pages/AdminModerationPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/admin/moderation" element={<AdminModerationPage />} />
    </Routes>
  )
}

export default App
