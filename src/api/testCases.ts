import { apiFetch } from './client'

export type TestCasePriority = 'high' | 'medium' | 'low'
export type TestCaseCategory = 'functional' | 'validation' | 'security' | 'accessibility'

export interface GeneratedTestCase {
  title: string
  requirement: string
  priority: TestCasePriority
  category: TestCaseCategory
  preconditions: string[]
  steps: string[]
  expected_result: string
}

export interface TestCaseGenerationResponse {
  project_id: number
  project_name: string
  provider: 'mistral'
  model: string
  test_cases: GeneratedTestCase[]
}

export async function generateProjectTestCases(projectId: number): Promise<TestCaseGenerationResponse> {
  if (!Number.isInteger(projectId) || projectId < 1) {
    throw new Error('Identifiant de projet invalide.')
  }
  return apiFetch<TestCaseGenerationResponse>(`/api/projects/${projectId}/test-cases/`, {
    method: 'POST',
    body: {},
  })
}
