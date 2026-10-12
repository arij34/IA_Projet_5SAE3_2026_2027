import FreelancerProfileForm from './FreelancerProfileForm'
import ProjectOwnerProfileForm from './ProjectOwnerProfileForm'
import type { ProfileUpdate, ProfileUser } from '../types'

type ProfileFormProps = {
  user: ProfileUser
  isSubmitting: boolean
  onSubmit: (value: ProfileUpdate) => void
}

function ProfileForm({ user, isSubmitting, onSubmit }: ProfileFormProps) {
  const initialValue: ProfileUpdate = {
    title: user.title,
    bio: user.bio,
    skills: user.skills,
    hourly_rate: user.hourly_rate,
    cv: null,
  }

  switch (user.role) {
    case 'FREELANCER':
      return <FreelancerProfileForm initialValue={initialValue} currentCvUrl={user.cv} isSubmitting={isSubmitting} onSubmit={onSubmit} />
    case 'PROJECT_OWNER':
      return <ProjectOwnerProfileForm initialValue={initialValue} isSubmitting={isSubmitting} onSubmit={onSubmit} />
    case 'ADMIN':
      return null
  }
}

export default ProfileForm
