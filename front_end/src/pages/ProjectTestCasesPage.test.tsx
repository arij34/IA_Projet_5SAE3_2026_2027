// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ProjectTestCasesPage from './ProjectTestCasesPage'
import { generateProjectTestCases } from '../api/testCases'

vi.mock('../api/testCases', () => ({ generateProjectTestCases: vi.fn() }))

afterEach(() => cleanup())

describe('ProjectTestCasesPage', () => {
  it('requests cases for the project in the route and displays the structured response', async () => {
    vi.mocked(generateProjectTestCases).mockResolvedValue({
      project_id: 42,
      project_name: 'Application de réservation',
      provider: 'mistral',
      model: 'ministral-14b-2512',
      test_cases: [{
        title: 'Réserver un créneau disponible',
        requirement: 'Un client peut réserver une séance.',
        priority: 'high',
        category: 'functional',
        preconditions: ['Un créneau futur est libre.'],
        steps: ['Choisir le créneau.', 'Confirmer la réservation.'],
        expected_result: 'La réservation est confirmée.',
      }],
    })

    render(
      <MemoryRouter initialEntries={['/projects/42/test-cases']}>
        <Routes><Route path="/projects/:projectId/test-cases" element={<ProjectTestCasesPage />} /></Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Générer les cas de test' }))

    await waitFor(() => expect(generateProjectTestCases).toHaveBeenCalledWith(42))
    expect(await screen.findByText('Réserver un créneau disponible', { exact: false })).toBeTruthy()
    expect(screen.getByText('La réservation est confirmée.')).toBeTruthy()
    expect(screen.getByText('ministral-14b-2512', { exact: false })).toBeTruthy()
  })

  it('shows a useful error when the service is not configured', async () => {
    const { ApiError } = await import('../api/client')
    vi.mocked(generateProjectTestCases).mockRejectedValue(
      new ApiError(503, { code: 'provider_not_configured' }),
    )
    render(
      <MemoryRouter initialEntries={['/projects/7/test-cases']}>
        <Routes><Route path="/projects/:projectId/test-cases" element={<ProjectTestCasesPage />} /></Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Générer les cas de test' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Mistral n’est pas configuré')
  })

  it('distinguishes Mistral rate limits from Freelancy generation limits', async () => {
    const { ApiError } = await import('../api/client')
    vi.mocked(generateProjectTestCases).mockRejectedValue(
      new ApiError(429, { code: 'provider_rate_limited' }),
    )
    render(
      <MemoryRouter initialEntries={['/projects/7/test-cases']}>
        <Routes><Route path="/projects/:projectId/test-cases" element={<ProjectTestCasesPage />} /></Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Générer les cas de test' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Mistral a temporairement limité')
  })
})
