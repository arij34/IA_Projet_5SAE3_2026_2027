import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import AdminModerationPage from './pages/AdminModerationPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
      </Route>
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/admin/moderation" element={<AdminModerationPage />} />
    </Routes>
  )
}

export default App
