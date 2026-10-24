// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../../api/client'
import ScoreBreakdown from '../components/ScoreBreakdown'
import TeamBuilderPanel from '../components/TeamBuilderPanel'
import ProjectFreelancerRecommendations from '../pages/ProjectFreelancerRecommendations'
import FreelancerProjectRecommendations from '../pages/FreelancerProjectRecommendations'
import type { FreelancerMatch, TeamProposal } from '../types'
import {
  inviteFreelancer,
  listMyRecommendations,
  listProjectFreelancers,
  listRecommendedProjects,
  respondToRecommendation,
} from '../services/matchingApi'

vi.mock('../../../api/projects', () => ({
  getProject: vi.fn(() => Promise.resolve({ id: 3, name: 'Plateforme interne' })),
  listProjects: vi.fn(() => Promise.resolve([])),
}))

vi.mock('../services/matchingApi', () => ({
  inviteFreelancer: vi.fn(),
  listMyRecommendations: vi.fn(),
  listProjectFreelancers: vi.fn(),
  listRecommendedProjects: vi.fn(),
  refreshProjectMatching: vi.fn(),
  respondToRecommendation: vi.fn(),
  getProjectTeam: vi.fn(),
}))

const match: FreelancerMatch = {
  freelancer_id: 7,
  username: 'alice',
  title: 'Développeuse Python',
  hourly_rate: 45,
  skills: ['Python', 'Django'],
  speciality: 'Python',
  required_level: 'CONFIRME',
  total_score: 78.5,
  deterministic_score: 78.5,
  semantic_score: null,
  semantic_available: false,
  mode: 'DETERMINISTIC',
  semantic_weight: 0,
  subscores: {
    skills: {
      available: true,
      score: 100,
      detail: 'Compétence couverte.',
      matched: ['python'],
      missing: [],
    },
    budget: {
      available: true,
      score: 60,
      detail: 'Tarif légèrement au-dessus du budget.',
    },
    level: { available: true, score: 75, detail: 'Niveau estimé SENIOR.' },
    quiz: {
      available: false,
      score: null,
      detail: 'Aucun quiz terminé : critère neutralisé.',
    },
  },
  applied_weights: { skills: 0.53, budget: 0.27, level: 0.2 },
  skipped_criteria: ['quiz'],
  speciality_scores: [{ speciality: 'Python', score: 78.5 }],
  explanations: ['Compétences : 100/100.', 'Quiz : non évalué.'],
  algorithm_version: 'matching-v1',
}

// Le nettoyage automatique n'est pas actif sans `globals` dans Vitest :
// chaque test repart donc d'un DOM vide.
afterEach(() => {
  cleanup()
})

function pageOf<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results }
}

describe('ScoreBreakdown', () => {
  it('affiche les quatre critères et signale ceux qui sont neutralisés', () => {
    render(
      <ScoreBreakdown subscores={match.subscores} weights={match.applied_weights} />,
    )
    expect(screen.getByText('100/100')).toBeTruthy()
    expect(screen.getByText('non évalué')).toBeTruthy()
    expect(
      screen.getByText('Aucun quiz terminé : critère neutralisé.'),
    ).toBeTruthy()
  })

  it('affiche le poids renormalisé de chaque critère disponible', () => {
    render(
      <ScoreBreakdown subscores={match.subscores} weights={match.applied_weights} />,
    )
    expect(screen.getAllByText(/Compétences · poids 53 %/).length).toBeGreaterThan(0)
  })
})

describe('TeamBuilderPanel', () => {
  const candidate = {
    freelancer_id: 7,
    username: 'alice',
    title: 'Développeuse back-end Python',
    hourly_rate: 50,
    score: 20,
    skill_score: 0,
    skill_covered: false,
    matched_skills: [],
    missing_skills: ['mobile'],
    estimated_cost: 6125,
    justification: '0 terme(s) de la spécialité sur 1 couverts.',
  }

  const assumptions = {
    duree_semaines: 7,
    heures_par_semaine: 35,
    taux_engagement: 0.5,
    heures_par_poste: 122.5,
    score_minimal: 40,
    score_competences_minimal: 50,
  }

  const base: TeamProposal = {
    fully_staffed: false,
    fully_covered: false,
    required_positions: 1,
    assigned_positions: 0,
    skill_covered_positions: 0,
    members: [],
    uncovered: [
      {
        speciality: 'Développement mobile',
        required: 1,
        assigned: 0,
        missing: 1,
        reason: 'aucun_candidat_suffisamment_compatible',
        best_candidate: candidate,
      },
    ],
    estimated_cost: null,
    estimated_cost_partial: false,
    budget_total: 2500,
    budget_source: 'budget_recommande',
    over_budget: false,
    alerts: ['Aucun candidat suffisamment compatible pour « Développement mobile ».'],
    assumptions,
    algorithm_version: 'matching-v1',
  }

  function renderPanel(team: TeamProposal) {
    return render(
      <MemoryRouter>
        <TeamBuilderPanel team={team} projectId={3} />
      </MemoryRouter>,
    )
  }

  it("n'annonce aucun poste attribué quand aucun candidat n'atteint le seuil", () => {
    renderPanel(base)
    // Deux compteurs distincts tombent à 0/1 : postes attribués et postes couverts.
    expect(screen.getAllByText('0/1').length).toBe(2)
    expect(screen.getByText(/aucun candidat n’atteint le seuil/)).toBeTruthy()
  })

  it('montre le meilleur candidat écarté plutôt que de le masquer', () => {
    renderPanel(base)
    expect(screen.getByText(/Meilleur profil écarté : alice/)).toBeTruthy()
    expect(screen.getByText(/Manque : mobile/)).toBeTruthy()
  })

  it('expose les hypothèses de durée, de charge et de tarif', () => {
    renderPanel(base)
    expect(screen.getByText(/7 semaine\(s\), 35 heures par semaine/)).toBeTruthy()
    expect(screen.getByText(/122.5 heures par poste/)).toBeTruthy()
    expect(screen.getByText(/jamais des tarifs horaires/)).toBeTruthy()
  })

  it('distingue poste attribué et compétences couvertes', () => {
    renderPanel({
      ...base,
      fully_staffed: true,
      assigned_positions: 1,
      skill_covered_positions: 0,
      members: [
        { ...candidate, speciality: 'Développement mobile', required_level: 'CONFIRME' },
      ],
      uncovered: [],
      estimated_cost: 6125,
      alerts: [],
    })
    expect(screen.getByText('1/1')).toBeTruthy()
    expect(screen.getByText('0/1')).toBeTruthy()
    expect(screen.getByText(/manque : mobile/)).toBeTruthy()
  })

  it('signale un dépassement budgétaire sans toucher aux autres indicateurs', () => {
    renderPanel({
      ...base,
      fully_staffed: true,
      fully_covered: true,
      assigned_positions: 1,
      skill_covered_positions: 1,
      members: [
        {
          ...candidate,
          skill_covered: true,
          missing_skills: [],
          speciality: 'Développement mobile',
          required_level: 'CONFIRME',
        },
      ],
      uncovered: [],
      estimated_cost: 6125,
      over_budget: true,
      alerts: [],
    })
    expect(screen.getByText('Budget dépassé')).toBeTruthy()
    expect(screen.getByText('Compétences couvertes')).toBeTruthy()
    expect(screen.getByText('Tous les postes attribués')).toBeTruthy()
  })

  it('indique la source du budget de référence', () => {
    renderPanel(base)
    expect(screen.getByText(/budget recommandé par l'analyse IA/)).toBeTruthy()
  })
})

describe('ProjectFreelancerRecommendations', () => {
  beforeEach(() => {
    vi.mocked(listProjectFreelancers).mockReset()
  })

  function renderPage() {
    return render(
      <MemoryRouter initialEntries={['/matching/projects/3/freelancers']}>
        <Routes>
          <Route
            path="/matching/projects/:projectId/freelancers"
            element={<ProjectFreelancerRecommendations />}
          />
        </Routes>
      </MemoryRouter>,
    )
  }

  it('affiche les freelances recommandés avec leur score', async () => {
    vi.mocked(listProjectFreelancers).mockResolvedValue(pageOf([match]))
    renderPage()
    await waitFor(() => expect(screen.getByText('alice')).toBeTruthy())
    expect(screen.getByText('79')).toBeTruthy()
  })

  it('affiche un état vide explicite', async () => {
    vi.mocked(listProjectFreelancers).mockResolvedValue(pageOf<FreelancerMatch>([]))
    renderPage()
    await waitFor(() =>
      expect(
        screen.getByText(/Aucun freelance validé ne correspond/),
      ).toBeTruthy(),
    )
  })

  it("explique qu'une analyse IA est requise", async () => {
    vi.mocked(listProjectFreelancers).mockRejectedValue(
      new ApiError(409, { code: 'analysis_required' }),
    )
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/doit d'abord être analysé/)).toBeTruthy(),
    )
  })

  it('affiche un message dédié en cas de refus serveur', async () => {
    vi.mocked(listProjectFreelancers).mockRejectedValue(new ApiError(403, {}))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/pas accessible avec votre compte/)).toBeTruthy(),
    )
  })

  it('affiche une erreur générique sur panne réseau', async () => {
    vi.mocked(listProjectFreelancers).mockRejectedValue(new Error('offline'))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/n'ont pas pu être chargées/)).toBeTruthy(),
    )
  })

  it('propose le retour aux projets et la composition d’équipe avec le bon identifiant', async () => {
    vi.mocked(listProjectFreelancers).mockResolvedValue(pageOf([match]))
    renderPage()
    await waitFor(() => expect(screen.getByText('alice')).toBeTruthy())
    const back = screen.getByRole('link', { name: /Retour à mes projets/ })
    const team = screen.getByRole('link', { name: /Composer une équipe/ })
    expect(back.getAttribute('href')).toBe('/matching/projects')
    expect(team.getAttribute('href')).toBe('/matching/projects/3/team')
  })

  it('indique la progression puis le succès de l’invitation', async () => {
    vi.mocked(listProjectFreelancers).mockResolvedValue(pageOf([match]))
    vi.mocked(inviteFreelancer).mockResolvedValue({
      id: 1,
      project: 3,
      project_name: 'Plateforme interne',
      freelancer: 7,
      freelancer_username: 'alice',
      speciality: 'Python',
      status: 'PROPOSED',
      score_snapshot: null,
      created_at: '',
      responded_at: null,
    })
    renderPage()
    await waitFor(() => expect(screen.getByText('alice')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /Inviter sur ce projet/ }))
    await waitFor(() =>
      expect(screen.getByText(/Invitation envoyée à alice/)).toBeTruthy(),
    )
    expect(
      screen.getByRole('button', { name: /Invitation envoyée/ }).hasAttribute('disabled'),
    ).toBe(true)
  })

  it('signale une invitation en échec sans bloquer la page', async () => {
    vi.mocked(listProjectFreelancers).mockResolvedValue(pageOf([match]))
    vi.mocked(inviteFreelancer).mockRejectedValue(new ApiError(400, {}))
    renderPage()
    await waitFor(() => expect(screen.getByText('alice')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /Inviter sur ce projet/ }))
    await waitFor(() =>
      expect(screen.getByText(/n'a pas pu être envoyée/)).toBeTruthy(),
    )
  })
})

describe('FreelancerProjectRecommendations', () => {
  beforeEach(() => {
    vi.mocked(listRecommendedProjects).mockReset()
    vi.mocked(listMyRecommendations).mockReset()
  })

  it('liste les projets recommandés et leurs spécialités', async () => {
    vi.mocked(listMyRecommendations).mockResolvedValue(pageOf([]))
    vi.mocked(listRecommendedProjects).mockResolvedValue(
      pageOf([
        {
          project_id: 3,
          name: 'Plateforme interne',
          description: 'Application web de gestion.',
          deadline: '2027-01-01',
          estimated_amount: '10000.00',
          budget_min: 8000,
          budget_max: 12000,
          duree_semaines: 10,
          required_specialities: [{ nom: 'Python', niveau: 'CONFIRME', nb: 1 }],
          match,
        },
      ]),
    )
    render(
      <MemoryRouter>
        <FreelancerProjectRecommendations />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Plateforme interne')).toBeTruthy())
    expect(screen.getByText(/Python · CONFIRME · 1 poste/)).toBeTruthy()
  })

  it('accepte une invitation et confirme la réponse', async () => {
    const invitation = {
      id: 12,
      project: 3,
      project_name: 'Plateforme interne',
      freelancer: 7,
      freelancer_username: 'alice',
      speciality: 'Python',
      status: 'PROPOSED' as const,
      score_snapshot: 78,
      created_at: '',
      responded_at: null,
    }
    vi.mocked(listMyRecommendations).mockResolvedValue(pageOf([invitation]))
    vi.mocked(listRecommendedProjects).mockResolvedValue(pageOf([]))
    vi.mocked(respondToRecommendation).mockResolvedValue({
      ...invitation,
      status: 'ACCEPTED',
    })
    render(
      <MemoryRouter>
        <FreelancerProjectRecommendations />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Accepter l'invitation/ })).toBeTruthy(),
    )
    fireEvent.click(screen.getByRole('button', { name: /Accepter l'invitation/ }))
    await waitFor(() =>
      expect(screen.getByText(/Vous avez accepté l'invitation/)).toBeTruthy(),
    )
  })

  it('affiche un état vide actionnable quand aucun projet ne correspond', async () => {
    vi.mocked(listMyRecommendations).mockResolvedValue(pageOf([]))
    vi.mocked(listRecommendedProjects).mockResolvedValue(pageOf([]))
    render(
      <MemoryRouter>
        <FreelancerProjectRecommendations />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByText(/Aucun projet publié et analysé/)).toBeTruthy(),
    )
    expect(
      screen.getByRole('link', { name: /Passer un challenge/ }).getAttribute('href'),
    ).toBe('/challenges')
    expect(screen.getByText(/aucune invitation en attente/)).toBeTruthy()
  })

  it('signale un profil non validé', async () => {
    vi.mocked(listMyRecommendations).mockRejectedValue(new ApiError(403, {}))
    vi.mocked(listRecommendedProjects).mockRejectedValue(new ApiError(403, {}))
    render(
      <MemoryRouter>
        <FreelancerProjectRecommendations />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByText(/doit être validé par un administrateur/)).toBeTruthy(),
    )
  })
})
