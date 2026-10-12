import { Link } from 'react-router-dom'

function AdminProfileView() {
  return (
    <section className="admin-profile-space">
      <h2>Espace administrateur</h2>
      <p>Gérez la modération des profils depuis votre espace d’administration.</p>
      <Link className="btn btn-primary" to="/admin/users">Accéder au dashboard de modération</Link>
    </section>
  )
}

export default AdminProfileView
