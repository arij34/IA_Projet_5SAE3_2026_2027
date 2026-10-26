import type { ProfileUser } from '../types'

function ProjectOwnerProfileView({ user }: { user: ProfileUser }) {
  return (
    <>
      <h2>Profil porteur de projet</h2>
      <dl className="profile-details">
        <div><dt>Nom du projet ou de l'entreprise</dt><dd>{user.title || 'Non renseigné'}</dd></div>
        <div><dt>Description du projet</dt><dd>{user.bio || 'Non renseignée'}</dd></div>
      </dl>
    </>
  )
}

export default ProjectOwnerProfileView
