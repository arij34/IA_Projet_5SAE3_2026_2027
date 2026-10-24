import type { ProfileUser } from '../types'

function FreelancerProfileView({ user }: { user: ProfileUser }) {
  return (
    <>
      <h2>Profil freelance</h2>
      <dl className="profile-details">
        <div><dt>Titre professionnel</dt><dd>{user.title || 'Non renseigné'}</dd></div>
        <div><dt>Présentation</dt><dd>{user.bio || 'Non renseignée'}</dd></div>
        <div><dt>Compétences</dt><dd>{user.skills.length > 0 ? user.skills.join(', ') : 'Non renseignées'}</dd></div>
        {user.cv && <div><dt>CV</dt><dd><a href={user.cv} target="_blank" rel="noreferrer">Télécharger mon CV</a></dd></div>}
      </dl>
    </>
  )
}

export default FreelancerProfileView
