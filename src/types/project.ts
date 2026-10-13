export type ProjectStatus = 'DRAFT' | 'ANALYZED' | 'PUBLISHED' | 'DECLINED'

export interface ProjectInput {
  name: string
  description: string
  deadline: string
  estimated_amount: string
}

export interface Project extends ProjectInput {
  id: number
  status: ProjectStatus
  owner?: number
  created_at: string
  updated_at: string
  title?: string
  date_limite?: string
  budget_min?: number
  budget_max?: number
  devise?: string
}

export interface AnalysisResult {
  budget_min: number
  budget_max: number
  devise: string
  nb_freelancers: number
  specialites: Specialty[]
  duree_semaines: number
  complexite: string
  risques: Risk[]
  jalons: Milestone[]
  coherence_budget: 'SOUS_ESTIME' | 'REALISTE' | 'SUR_ESTIME' | string
  recommandation: string
  confiance: number
  score_complexite: number
  facteurs_complexite: string[]
  duree_min_semaines: number
  duree_max_semaines: number
  budget_recommande: number
  justification: string
  phases: Phase[]
  faisabilite_deadline: 'TENABLE' | 'SERREE' | 'IRREALISTE' | string
  faisabilite_deadline_justification: string
  taux_reussite: number
  facteurs_positifs: string[]
  facteurs_negatifs: string[]
  hypotheses: string[]
  questions_clarification: string[]
  recommandations: string[]
  references_used?: string[]
}

export interface AnalysisResponse {
  result: AnalysisResult | null
  simulated: boolean
  error: string | null
  analyzed_at: string
}

export interface ChatbotResponse {
  answer: string
  sources: string[]
  simulated: boolean
  error?: string
}

export interface Risk {
  description: string
  probabilite: number
  impact: string
  mitigation: string
}

export interface Milestone {
  nom: string
  semaine: number
}

export interface Specialty {
  nom: string
  nb: number
  niveau: string
  charge_pourcentage: number
}

export interface Phase {
  nom: string
  objectif: string
  duree_semaines: number
  livrables: string[]
  specialites: string[]
  budget_pourcentage: number
}

export interface PublicProject extends Project {
  published_at?: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
