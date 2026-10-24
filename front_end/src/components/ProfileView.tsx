import AdminProfileView from './AdminProfileView'
import FreelancerProfileView from './FreelancerProfileView'
import ProjectOwnerProfileView from './ProjectOwnerProfileView'
import type { ProfileUser } from '../types'

function ProfileView({ user }: { user: ProfileUser }) {
  switch (user.role) {
    case 'FREELANCER':
      return <FreelancerProfileView user={user} />
    case 'PROJECT_OWNER':
      return <ProjectOwnerProfileView user={user} />
    case 'ADMIN':
      return <AdminProfileView />
  }
}

export default ProfileView
