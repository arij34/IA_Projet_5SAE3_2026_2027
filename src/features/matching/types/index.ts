/** Types du module matching, alignés sur les réponses de /api/matching/. */

export type MatchMode = 'HYBRID' | 'DETERMINISTIC'

export type SubscoreKey = 'skills' | 'budget' | 'level' | 'quiz'

export interface Subscore {
  available: boolean
  score: number | null
  detail?: string
  matched?: string[]
  missing?: string[]
  affordable_rate?: number | null
  hourly_rate?: number | null
  required_level?: string | null
  estimated_level?: string | null
  estimation_source?: string
  source?: string
  categories?: { category: string; name: string; average: number; attempts: number }[]
}

export interface SpecialityScore {
  speciality: string
  score: number
}

export interface FreelancerMatch {
  freelancer_id: number
  username: string
  title: string
  hourly_rate: number | null
  skills: string[]
  speciality: string
  required_level: string | null
  total_score: number
  deterministic_score: number
  semantic_score: number | null
  semantic_available: boolean
  semantic_justification?: string | null
  semantic_concepts?: string[]
  mode: MatchMode
  semantic_weight: number
  subscores: Partial<Record<SubscoreKey, Subscore>>
  applied_weights: Partial<Record<SubscoreKey, number>>
  skipped_criteria: string[]
  speciality_scores: SpecialityScore[]
  explanations: string[]
  algorithm_version: string
  smart_explanation?: {
    strengths: string[]
    missing_or_unverified: string[]
    recommendation: string
  } | null
}

export interface SmartMatchCriteria {
  skills: string[]
  budget: number | null
  duration_weeks: number | null
  level: string | null
}

export interface RequiredSpeciality {
  nom: string
  niveau: string
  nb: number
}

export interface RecommendedProject {
  project_id: number
  name: string
  description: string
  deadline: string
  estimated_amount: string
  budget_min?: number | null
  budget_max?: number | null
  duree_semaines?: number | null
  required_specialities: RequiredSpeciality[]
  match: FreelancerMatch
}

export interface TeamCandidate {
  freelancer_id: number
  username: string
  title: string
  hourly_rate: number | null
  score: number
  skill_score: number | null
  skill_covered: boolean
  matched_skills: string[]
  missing_skills: string[]
  estimated_cost: number | null
  justification: string
}

export interface TeamMember extends TeamCandidate {
  speciality: string | null
  required_level: string | null
}

export type UncoveredReason =
  | 'aucun_candidat_disponible'
  | 'aucun_candidat_suffisamment_compatible'
  | 'candidats_insuffisants_en_nombre'

export interface UncoveredSpeciality {
  speciality: string
  required: number
  assigned: number
  missing: number
  reason: UncoveredReason
  best_candidate: TeamCandidate | null
}

export interface TeamAssumptions {
  duree_semaines: number | null
  heures_par_semaine: number
  taux_engagement: number
  heures_par_poste: number | null
  score_minimal: number
  score_competences_minimal: number
}

export interface TeamProposal {
  fully_staffed: boolean
  fully_covered: boolean
  required_positions: number
  assigned_positions: number
  skill_covered_positions: number
  members: TeamMember[]
  uncovered: UncoveredSpeciality[]
  estimated_cost: number | null
  estimated_cost_partial: boolean
  budget_total: number | null
  budget_source: string
  over_budget: boolean
  alerts: string[]
  assumptions: TeamAssumptions
  algorithm_version: string
}

export interface Recommendation {
  id: number
  project: number
  project_name: string
  freelancer: number
  freelancer_username: string
  speciality: string
  status: 'PROPOSED' | 'ACCEPTED' | 'DECLINED'
  score_snapshot: number | null
  created_at: string
  responded_at: string | null
}

export interface MatchingPage<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
