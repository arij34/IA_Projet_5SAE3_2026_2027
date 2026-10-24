import { useEffect, useState, type FormEvent } from 'react'
import { Loader2, Pencil, Plus, Save, Trash2, WandSparkles } from 'lucide-react'
import { ApiError } from '../../api/client'
import {
  deletePlanningTask,
  generatePlanning,
  getPlanning,
  listPlannings,
  savePlanning,
  updatePlanningTask,
} from './planningApi'
import type { PlanningProject, PlanningTask, PlanningTaskInput } from './planningApi'
import './planning.css'

type TaskField = keyof PlanningTaskInput
type TaskErrors = Partial<Record<TaskField, string>>

const emptyTask = (): PlanningTaskInput => ({ name: '', description: '', start_date: '', end_date: '' })

function dateOffset(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 10)
}

function validateTask(task: PlanningTaskInput): TaskErrors {
  const errors: TaskErrors = {}
  const isIsoDate = (value: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
    const parsed = new Date(`${value}T00:00:00Z`)
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
  }
  const name = task.name.trim()
  if (!name) errors.name = 'Le nom est obligatoire.'
  else if (name.length < 3 || name.length > 100) errors.name = 'Le nom doit contenir de 3 à 100 caractères.'
  if (!task.description.trim()) errors.description = 'La description est obligatoire.'
  if (!task.start_date) errors.start_date = 'La date de début est obligatoire.'
  else if (!isIsoDate(task.start_date)) errors.start_date = 'Entrez une date valide.'
  if (!task.end_date) errors.end_date = 'La date de fin est obligatoire.'
  else if (!isIsoDate(task.end_date)) errors.end_date = 'Entrez une date valide.'
  else if (task.start_date && task.end_date < task.start_date) errors.end_date = 'La date de fin ne peut pas précéder la date de début.'
  return errors
}

function readableError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.data && typeof error.data === 'object') {
    const data = error.data as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  }
  return error instanceof Error ? error.message : fallback
}

interface TaskModalProps {
  initial: PlanningTaskInput
  title: string
  onClose: () => void
  onSubmit: (task: PlanningTaskInput) => void
}

function TaskModal({ initial, title, onClose, onSubmit }: TaskModalProps) {
  const [task, setTask] = useState(initial)
  const [errors, setErrors] = useState<TaskErrors>({})

  const change = (field: TaskField, value: string) => {
    setTask((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateTask(task)
    setErrors(validation)
    if (Object.keys(validation).length === 0) onSubmit(task)
  }

  return (
    <div className="planning-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="planning-modal" role="dialog" aria-modal="true" aria-labelledby="planning-task-modal-title">
        <h2 id="planning-task-modal-title">{title}</h2>
        <form onSubmit={submit} noValidate>
          <label htmlFor="planning-task-name">Nom</label>
          <input id="planning-task-name" className="form-input" maxLength={100} value={task.name} onChange={(event) => change('name', event.target.value)} aria-invalid={Boolean(errors.name)} />
          {errors.name && <small className="field-error">{errors.name}</small>}

          <label htmlFor="planning-task-description">Description</label>
          <textarea id="planning-task-description" className="form-input" rows={4} value={task.description} onChange={(event) => change('description', event.target.value)} aria-invalid={Boolean(errors.description)} />
          {errors.description && <small className="field-error">{errors.description}</small>}

          <div className="planning-date-fields">
            <div>
              <label htmlFor="planning-task-start">Date de début</label>
              <input id="planning-task-start" className="form-input" type="date" value={task.start_date} onChange={(event) => change('start_date', event.target.value)} aria-invalid={Boolean(errors.start_date)} />
              {errors.start_date && <small className="field-error">{errors.start_date}</small>}
            </div>
            <div>
              <label htmlFor="planning-task-end">Date de fin</label>
              <input id="planning-task-end" className="form-input" type="date" value={task.end_date} onChange={(event) => change('end_date', event.target.value)} aria-invalid={Boolean(errors.end_date)} />
              {errors.end_date && <small className="field-error">{errors.end_date}</small>}
            </div>
          </div>
          <div className="planning-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Annuler</button>
            <button type="submit" className="btn btn-primary">Enregistrer la tâche</button>
          </div>
        </form>
      </section>
    </div>
  )
}

function PlanningPage() {
  const [projectName, setProjectName] = useState('')
  const [tasks, setTasks] = useState<PlanningTaskInput[]>([])
  const [hasDraft, setHasDraft] = useState(false)
  const [simulated, setSimulated] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)
  const [taskErrors, setTaskErrors] = useState<TaskErrors[]>([])
  const [notice, setNotice] = useState<{ text: string; tone: 'success' | 'error' | 'info' } | null>(null)
  const [modal, setModal] = useState<{ index: number | null; initial: PlanningTaskInput } | null>(null)
  const [savedPlans, setSavedPlans] = useState<PlanningProject[]>([])
  const [plansLoading, setPlansLoading] = useState(true)
  const [plansError, setPlansError] = useState<string | null>(null)
  const [loadingPlanId, setLoadingPlanId] = useState<number | null>(null)

  const refreshSavedPlans = async () => {
    setPlansLoading(true)
    setPlansError(null)
    try {
      setSavedPlans(await listPlannings())
    } catch (error: unknown) {
      setPlansError(readableError(error, 'Impossible de charger les plannings enregistrés.'))
    } finally {
      setPlansLoading(false)
    }
  }

  useEffect(() => {
    void refreshSavedPlans()
  }, [])

  const validateProjectName = () => {
    const trimmed = projectName.trim()
    if (!trimmed) {
      setNameError('Le nom du projet est obligatoire.')
      return false
    }
    if (trimmed.length > 100) {
      setNameError('Le nom ne peut pas dépasser 100 caractères.')
      return false
    }
    setNameError(null)
    return true
  }

  const handleGenerate = async () => {
    if (!validateProjectName()) return
    setIsGenerating(true)
    setNotice(null)
    try {
      const result = await generatePlanning(projectName.trim())
      setTasks(result.tasks)
      setHasDraft(true)
      setTaskErrors([])
      setSimulated(result.simulated)
      setNotice(result.simulated
        ? { text: 'Analyse simulée : voici un planning de secours modifiable.', tone: 'info' }
        : { text: 'Les trois tâches proposées sont prêtes à être modifiées.', tone: 'success' })
    } catch (error: unknown) {
      setNotice({ text: readableError(error, 'La génération du planning a échoué.'), tone: 'error' })
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSave = async () => {
    if (!validateProjectName()) return
    const validation = tasks.map(validateTask)
    setTaskErrors(validation)
    if (validation.some((errors) => Object.keys(errors).length > 0)) {
      setNotice({ text: 'Corrigez les champs signalés avant d’enregistrer.', tone: 'error' })
      return
    }
    setIsSaving(true)
    setNotice(null)
    try {
      await savePlanning(projectName.trim(), tasks.map((task) => ({
        name: task.name.trim(),
        description: task.description.trim(),
        start_date: task.start_date,
        end_date: task.end_date,
      })))
      setNotice({ text: 'Planning enregistré avec succès.', tone: 'success' })
      await refreshSavedPlans()
    } catch (error: unknown) {
      setNotice({ text: readableError(error, 'Impossible d’enregistrer le planning.'), tone: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const openAddTask = () => setModal({
    index: null,
    initial: { ...emptyTask(), start_date: dateOffset(0), end_date: dateOffset(2) },
  })

  const submitModal = (task: PlanningTaskInput) => {
    setTasks((current) => {
      if (modal?.index === null) return [...current, task]
      if (modal?.index === undefined) return current
      return current.map((item, index) => index === modal.index ? task : item)
    })
    setTaskErrors([])
    setModal(null)
    setNotice(null)
  }

  const editTask = (index: number) => setModal({ index, initial: { ...tasks[index] } })

  const deleteTask = (index: number) => {
    const task = tasks[index]
    if (!window.confirm(`Supprimer la tâche « ${task.name} » ?`)) return
    setTasks((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setTaskErrors((current) => current.filter((_, itemIndex) => itemIndex !== index))
  }

  const loadSavedPlan = async (id: number) => {
    setLoadingPlanId(id)
    setNotice(null)
    try {
      const project = await getPlanning(id)
      setProjectName(project.name)
      setTasks(project.tasks.map(({ name, description, start_date, end_date }) => ({ name, description, start_date, end_date })))
      setHasDraft(true)
      setSimulated(false)
      setTaskErrors([])
      setNotice({ text: 'Planning chargé en brouillon. Enregistrer créera une nouvelle copie.', tone: 'info' })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (error: unknown) {
      setNotice({ text: readableError(error, 'Impossible de charger ce planning.'), tone: 'error' })
    } finally {
      setLoadingPlanId(null)
    }
  }

  const removeSavedTask = async (plan: PlanningProject, task: PlanningTask) => {
    if (!window.confirm(`Supprimer définitivement « ${task.name} » du planning enregistré ?`)) return
    try {
      await deletePlanningTask(plan.id, task.id)
      setSavedPlans((current) => current.map((item) => item.id === plan.id
        ? { ...item, tasks: item.tasks.filter((savedTask) => savedTask.id !== task.id) }
        : item))
      setNotice({ text: 'Tâche supprimée du planning enregistré.', tone: 'success' })
    } catch (error: unknown) {
      setNotice({ text: readableError(error, 'La suppression de cette tâche a échoué.'), tone: 'error' })
    }
  }

  const editSavedTask = async (plan: PlanningProject, task: PlanningTask) => {
    setModal({
      index: null,
      initial: { name: task.name, description: task.description, start_date: task.start_date, end_date: task.end_date },
    })
    // The modal is draft-only; saved tasks are changed only by the explicit action below.
    // Keep the selected records in memory for the task-update callback.
    setSelectedSavedTask({ project: plan, task })
  }

  const [selectedSavedTask, setSelectedSavedTask] = useState<{ project: PlanningProject; task: PlanningTask } | null>(null)

  const submitSavedTaskEdit = async (task: PlanningTaskInput) => {
    if (!selectedSavedTask) return
    try {
      const { project, task: originalTask } = selectedSavedTask
      const updated = await updatePlanningTask(project.id, originalTask.id, task)
      setSavedPlans((current) => current.map((plan) => plan.id === project.id
        ? { ...plan, tasks: plan.tasks.map((savedTask) => savedTask.id === originalTask.id ? updated : savedTask) }
        : plan))
      setNotice({ text: 'Tâche mise à jour.', tone: 'success' })
    } catch (error: unknown) {
      setNotice({ text: readableError(error, 'La mise à jour de cette tâche a échoué.'), tone: 'error' })
    } finally {
      setSelectedSavedTask(null)
      setModal(null)
    }
  }

  const handleModalSubmit = (task: PlanningTaskInput) => {
    if (selectedSavedTask) {
      void submitSavedTaskEdit(task)
      return
    }
    submitModal(task)
  }

  return (
    <main className="page-shell planning-page">
      <section className="card page-card">
        <div className="auth-heading">
          <div className="auth-icon"><WandSparkles aria-hidden="true" size={24} /></div>
          <h1>Planning de projet</h1>
          <p>Saisissez un nom de projet pour générer trois tâches modifiables.</p>
        </div>

        {notice && <p className={`alert alert-${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'}>{notice.text}</p>}

        <div className="form-group">
          <label htmlFor="planning-project-name">Nom du projet</label>
          <input
            id="planning-project-name"
            className="form-input"
            maxLength={100}
            value={projectName}
            onChange={(event) => { setProjectName(event.target.value); setNameError(null) }}
            aria-invalid={Boolean(nameError)}
          />
          {nameError && <small className="field-error">{nameError}</small>}
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void handleGenerate()} disabled={isGenerating || isSaving}>
          {isGenerating ? <><Loader2 className="spin" size={18} aria-hidden="true" /> Génération en cours…</> : <><WandSparkles size={18} aria-hidden="true" /> Générer avec l’IA</>}
        </button>

        {simulated && hasDraft && <p className="planning-simulated" role="status">Analyse simulée</p>}

        {hasDraft && (
          <section className="planning-draft" aria-labelledby="planning-draft-title">
            <div className="planning-section-heading">
              <div>
                <h2 id="planning-draft-title">Brouillon du planning</h2>
                <p>{tasks.length} tâche{tasks.length > 1 ? 's' : ''} modifiable{tasks.length > 1 ? 's' : ''} · Rien n’est enregistré avant votre validation.</p>
              </div>
              <button type="button" className="btn btn-secondary" onClick={openAddTask}>
                <Plus size={17} aria-hidden="true" /> Ajouter une tâche
              </button>
            </div>
            <div className="planning-task-list">
              {tasks.map((task, index) => {
                const errors = taskErrors[index] ?? {}
                return (
                  <article className="planning-task-card" key={`${index}-${task.name}`}>
                    <div className="planning-task-copy">
                      <span className="planning-task-number">Tâche {index + 1}</span>
                      <h3>{task.name}</h3>
                      {errors.name && <small className="field-error">{errors.name}</small>}
                      <p>{task.description}</p>
                      {errors.description && <small className="field-error">{errors.description}</small>}
                      <p className="planning-task-dates">
                        {task.start_date || 'Date à définir'} → {task.end_date || 'Date à définir'}
                      </p>
                      {(errors.start_date || errors.end_date) && <small className="field-error">{errors.start_date ?? errors.end_date}</small>}
                    </div>
                    <div className="planning-task-actions">
                      <button type="button" className="btn btn-secondary" onClick={() => editTask(index)} aria-label={`Modifier ${task.name}`}><Pencil size={16} aria-hidden="true" /> Modifier</button>
                      <button type="button" className="btn btn-secondary planning-delete" onClick={() => deleteTask(index)} aria-label={`Supprimer ${task.name}`}><Trash2 size={16} aria-hidden="true" /> Supprimer</button>
                    </div>
                  </article>
                )
              })}
            </div>
            <button type="button" className="btn btn-primary planning-save" onClick={() => void handleSave()} disabled={isSaving || isGenerating}>
              {isSaving ? <><Loader2 className="spin" size={18} aria-hidden="true" /> Enregistrement…</> : <><Save size={18} aria-hidden="true" /> Enregistrer le planning</>}
            </button>
          </section>
        )}
      </section>

      <section className="card page-card planning-saved" aria-labelledby="saved-planning-title">
        <h2 id="saved-planning-title">Plannings enregistrés</h2>
        {plansLoading ? <p className="loading-state"><Loader2 className="spin" size={18} aria-hidden="true" /> Chargement des plannings…</p> : null}
        {plansError && <p className="alert alert-error" role="alert">{plansError}</p>}
        {!plansLoading && !plansError && savedPlans.length === 0 && <p className="planning-muted">Aucun planning enregistré pour le moment.</p>}
        <div className="planning-saved-list">
          {savedPlans.map((plan) => (
            <article className="planning-saved-item" key={plan.id}>
              <div className="planning-saved-header">
                <div>
                  <h3>{plan.name}</h3>
                  <p>{plan.tasks.length} tâche{plan.tasks.length === 1 ? '' : 's'} · Enregistré le {new Date(plan.created_at).toLocaleDateString('fr-FR')}</p>
                </div>
                <button type="button" className="btn btn-secondary" onClick={() => void loadSavedPlan(plan.id)} disabled={loadingPlanId !== null}>
                  {loadingPlanId === plan.id ? 'Chargement…' : 'Copier en brouillon'}
                </button>
              </div>
              {plan.tasks.length > 0 ? (
                <ul className="planning-saved-task-list">
                  {plan.tasks.map((task, index) => (
                    <li className="planning-saved-task-row" key={task.id}>
                      <div className="planning-saved-task-info">
                        <span className="planning-task-number">Tâche {index + 1}</span>
                        <span className="planning-saved-task-title">{task.name}</span>
                        <span className="planning-saved-task-dates">{task.start_date} → {task.end_date}</span>
                      </div>
                      <div className="planning-saved-task-actions">
                        <button type="button" className="planning-icon-button" aria-label={`Modifier la tâche enregistrée ${task.name}`} onClick={() => void editSavedTask(plan, task)}><Pencil size={15} aria-hidden="true" /></button>
                        <button type="button" className="planning-icon-button planning-delete" aria-label={`Supprimer la tâche enregistrée ${task.name}`} onClick={() => void removeSavedTask(plan, task)}><Trash2 size={15} aria-hidden="true" /></button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <p className="planning-saved-empty">Aucune tâche enregistrée dans ce planning.</p>}
            </article>
          ))}
        </div>
      </section>
      {modal && <TaskModal initial={modal.initial} title={modal.index === null && !selectedSavedTask ? 'Ajouter une tâche' : 'Modifier une tâche'} onClose={() => { setModal(null); setSelectedSavedTask(null) }} onSubmit={handleModalSubmit} />}
    </main>
  )
}

export default PlanningPage
