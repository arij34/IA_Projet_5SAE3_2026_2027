export type Role = 'FREELANCER' | 'PROJECT_OWNER' | 'ADMIN'

export type ModerationStatus = 'PENDING' | 'OK' | 'SUSPECT' | 'REJETE'

export interface User {
  id: number
  username: string
  email: string
  role: Role
  moderation_status: ModerationStatus
}

export interface ProfileUser extends User {
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
  cv: string | null
}

export type ProfileUpdate = {
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
  cv: File | null
}

export interface ModerationProfile {
  id: number
  username: string
  email: string
  role: Role
  title: string
  bio: string
  skills: string[]
  hourly_rate: number | null
  cv: string | null
  moderation_status: ModerationStatus
  last_analysis: ModerationAnalysis | null
}

export type AnalysisDecision = 'OK' | 'SUSPECT' | 'REJETE'

export interface ModerationAnalysis {
  decision: AnalysisDecision
  reason: string
  confidence_percent: number | null
  analyzed_at: string
  error: string
  simulated: boolean
  criteria: ModerationCriterion[]
}

export interface ModerationCriterion {
  id: string
  probleme: boolean
  commentaire: string
}
