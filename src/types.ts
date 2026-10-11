export type Role = 'FREELANCER' | 'PROJECT_OWNER' | 'ADMIN'

export type ModerationStatus = 'PENDING' | 'OK' | 'SUSPECT' | 'REJETE'

export interface User {
  id: number
  username: string
  email: string
  role: Role
  moderation_status: ModerationStatus
}
