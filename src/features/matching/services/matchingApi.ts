/**
 * Appels HTTP du module matching.
 *
 * Le client HTTP partagé et le stockage de jeton existants sont réutilisés :
 * aucune seconde authentification n'est introduite.
 */

import { apiFetch } from '../../../api/client'
import type {
  FreelancerMatch,
  MatchingPage,
  Recommendation,
  RecommendedProject,
  TeamProposal,
  SmartMatchCriteria,
} from '../types'

const BASE = '/api/matching'

export function smartMatchProject(
  projectId: number,
  description: string,
): Promise<{ criteria: SmartMatchCriteria | null; criteria_available: boolean; results: FreelancerMatch[] }> {
  return apiFetch(`${BASE}/projects/${projectId}/smart-match/`, {
    method: 'POST',
    body: { description },
  })
}

interface ListOptions {
  page?: number
  pageSize?: number
  semantic?: boolean
}

function buildQuery(options: ListOptions = {}): string {
  const query = new URLSearchParams()
  if (options.page && options.page > 1) query.set('page', String(options.page))
  if (options.pageSize) query.set('page_size', String(options.pageSize))
  if (options.semantic) query.set('semantic', 'true')
  const suffix = query.toString()
  return suffix ? `?${suffix}` : ''
}

/** Liste paginée des freelances recommandés pour un projet du porteur. */
export function listProjectFreelancers(
  projectId: number,
  options: ListOptions = {},
): Promise<MatchingPage<FreelancerMatch>> {
  return apiFetch<MatchingPage<FreelancerMatch>>(
    `${BASE}/projects/${projectId}/freelancers/${buildQuery(options)}`,
  )
}

/** Scores déjà calculés et enregistrés pour un projet. */
export function listProjectScores(
  projectId: number,
  options: ListOptions = {},
): Promise<MatchingPage<unknown>> {
  return apiFetch<MatchingPage<unknown>>(
    `${BASE}/projects/${projectId}/scores/${buildQuery(options)}`,
  )
}

/** Recalcule et persiste les scores d'un projet. */
export function refreshProjectMatching(
  projectId: number,
  semantic = false,
): Promise<{
  computed: number
  stored: number
  semantic_unavailable: boolean
  results: FreelancerMatch[]
}> {
  return apiFetch(`${BASE}/projects/${projectId}/refresh/${buildQuery({ semantic })}`, {
    method: 'POST',
  })
}

/** Proposition d'équipe couvrant les spécialités du projet. */
export function getProjectTeam(projectId: number): Promise<TeamProposal> {
  return apiFetch<TeamProposal>(`${BASE}/projects/${projectId}/team/`)
}

/** Projets publiés recommandés au freelance connecté. */
export function listRecommendedProjects(
  options: ListOptions = {},
): Promise<MatchingPage<RecommendedProject>> {
  return apiFetch<MatchingPage<RecommendedProject>>(
    `${BASE}/recommended-projects/${buildQuery(options)}`,
  )
}

/** Invite un freelance recommandé sur un projet. */
export function inviteFreelancer(
  projectId: number,
  freelancerId: number,
  speciality = '',
): Promise<Recommendation> {
  return apiFetch<Recommendation>(
    `${BASE}/projects/${projectId}/recommendations/`,
    { method: 'POST', body: { freelancer_id: freelancerId, speciality } },
  )
}

/** Recommandations reçues par le freelance connecté. */
export function listMyRecommendations(
  options: ListOptions = {},
): Promise<MatchingPage<Recommendation>> {
  return apiFetch<MatchingPage<Recommendation>>(
    `${BASE}/recommendations/${buildQuery(options)}`,
  )
}

/** Répond à une recommandation reçue. */
export function respondToRecommendation(
  recommendationId: number,
  decision: 'accept' | 'decline',
): Promise<Recommendation> {
  return apiFetch<Recommendation>(
    `${BASE}/recommendations/${recommendationId}/respond/`,
    { method: 'POST', body: { decision } },
  )
}
