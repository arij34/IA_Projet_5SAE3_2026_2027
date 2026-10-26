import { apiFetch } from '../../api/client'

export interface PlanningTaskInput {
  name: string
  description: string
  start_date: string
  end_date: string
}

export interface PlanningTask extends PlanningTaskInput {
  id: number
}

export interface PlanningProject {
  id: number
  name: string
  created_at: string
  tasks: PlanningTask[]
}

export interface GeneratedPlanning {
  tasks: PlanningTaskInput[]
  simulated: boolean
}

export function generatePlanning(projectName: string): Promise<GeneratedPlanning> {
  return apiFetch('/api/planning/generate/', {
    method: 'POST',
    body: { project_name: projectName },
  })
}

export function savePlanning(
  name: string,
  tasks: PlanningTaskInput[],
): Promise<PlanningProject> {
  return apiFetch('/api/planning/', {
    method: 'POST',
    body: { name, tasks },
  })
}

export function listPlannings(): Promise<PlanningProject[]> {
  return apiFetch('/api/planning/', { method: 'GET' })
}

export function getPlanning(id: number): Promise<PlanningProject> {
  return apiFetch(`/api/planning/${id}/`, { method: 'GET' })
}

export function updatePlanningTask(
  projectId: number,
  taskId: number,
  task: PlanningTaskInput,
): Promise<PlanningTask> {
  return apiFetch(`/api/planning/${projectId}/tasks/${taskId}/`, {
    method: 'PATCH',
    body: task,
  })
}

export function deletePlanningTask(projectId: number, taskId: number): Promise<void> {
  return apiFetch(`/api/planning/${projectId}/tasks/${taskId}/`, { method: 'DELETE' })
}
