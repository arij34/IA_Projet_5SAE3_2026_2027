import { type FormEvent, useEffect, useState } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, CircleAlert, Clock3, Info, Loader2, Sparkles, Users } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  analyzeProject,
  ApiError,
  createProject,
  declineProject,
  getProject,
  publishProject,
  updateProject,
} from '../api/projects'
import type { AnalysisResponse, Project, ProjectInput } from '../types/project'

type FormValues = {
  name: string
  description: string
  deadline: string
  amount: string
}

type FormErrors = Partial<Record<keyof FormValues, string>>

function validateForm(values: FormValues): FormErrors {
  const errors: FormErrors = {}
  const deadline = values.deadline ? new Date(values.deadline) : null
  const normalizedAmount = values.amount.trim().replace(',', '.')
  const amount = Number(normalizedAmount)

  if (!values.name.trim()) errors.name = 'Le nom est obligatoire.'
  else if (values.name.trim().length > 150) errors.name = 'Le nom ne peut pas dépasser 150 caractères.'

  if (!values.description.trim()) errors.description = 'La description est obligatoire.'
  else if (values.description.trim().length > 3000) {
    errors.description = 'La description ne peut pas dépasser 3000 caractères.'
  }

  if (!values.deadline) errors.deadline = 'La date limite est obligatoire.'
  else if (!deadline || Number.isNaN(deadline.getTime()) || deadline <= new Date()) {
    errors.deadline = 'La date limite doit être ultérieure à aujourd’hui.'
  }

  if (!values.amount.trim()) errors.amount = 'Le montant estimé est obligatoire.'
  else if (!Number.isFinite(amount) || amount <= 0) {
    errors.amount = 'Le montant estimé doit être supérieur à 0.'
  }

  return errors
}

function formatAmount(value: number): string {
  if (!Number.isFinite(value)) return 'Non renseigné'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

function complexityLabel(value: string): string {
  switch (value.toUpperCase()) {
    case 'FAIBLE': return 'Faible'
    case 'MOYENNE': return 'Moyenne'
    case 'ELEVEE': return 'Élevée'
    case 'TRES_ELEVEE': return 'Très élevée'
    default: return value
  }
}

function complexityClass(value: string): string {
  switch (value.toUpperCase()) {
    case 'FAIBLE': return 'badge-ok'
    case 'MOYENNE': return 'badge-suspect'
    case 'ELEVEE':
    case 'TRES_ELEVEE': return 'badge-rejete'
    default: return 'badge-neutral'
  }
}

function percentage(value: number): number {
  if (!Number.isFinite(value)) return 0
  return value <= 1 ? value * 100 : value
}

function frenchLevel(value: string): string {
  switch (value.toUpperCase()) {
    case 'FAIBLE': return 'Faible'
    case 'MOYEN': return 'Moyen'
    case 'ELEVE':
    case 'ELEVEE': return 'Élevé'
    default: return value
  }
}

function riskSeverity(risk: { impact: string; probabilite: number }): number {
  const impact = risk.impact.toUpperCase()
  const impactScore = impact === 'ELEVE' || impact === 'ELEVEE' ? 3 : impact === 'MOYEN' || impact === 'MOYENNE' ? 2 : 1
  return impactScore * 100 + (Number.isFinite(risk.probabilite) ? risk.probabilite : 0)
}

function NewProjectPage() {
  const navigate = useNavigate()
  const { projectId: projectIdParam } = useParams<{ projectId: string }>()
  const editingProjectId = projectIdParam ? Number(projectIdParam) : null
  const isEditing = editingProjectId !== null && Number.isInteger(editingProjectId)
  const [values, setValues] = useState<FormValues>({
    name: '',
    description: '',
    deadline: '',
    amount: '',
  })
  const [formErrors, setFormErrors] = useState<FormErrors>({})
  const [apiError, setApiError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [projectId, setProjectId] = useState<number | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isFinalizing, setIsFinalizing] = useState(false)
  const [isLoadingProject, setIsLoadingProject] = useState(isEditing)
  const [projectStatus, setProjectStatus] = useState<Project['status'] | null>(null)
  const [today] = useState(() => new Date())

  useEffect(() => {
    if (!isEditing || editingProjectId === null) return
    void getProject(editingProjectId)
      .then((project) => {
        setValues({
          name: project.name,
          description: project.description,
          deadline: project.deadline,
          amount: project.estimated_amount,
        })
        setProjectStatus(project.status)
        setProjectId(project.id)
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Impossible de charger le projet.')
      })
      .finally(() => setIsLoadingProject(false))
  }, [editingProjectId, isEditing])

  const updateValue = (field: keyof FormValues, value: string) => {
    setValues((current) => ({ ...current, [field]: value }))
    setFormErrors((current) => ({ ...current, [field]: undefined }))
    setApiError(null)
  }

  const analyzeWithTimeout = async (id: number): Promise<AnalysisResponse> => {
    let timeoutId: number | undefined
    const timeout = new Promise<never>((_, reject) => {
      // Gemini peut faire deux tentatives de 20 s ; garder une marge pour la réponse HTTP.
      timeoutId = window.setTimeout(() => reject(new Error('ANALYSIS_TIMEOUT')), 55_000)
    })

    try {
      return await Promise.race([analyzeProject(id), timeout])
    } finally {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors = validateForm(values)
    setFormErrors(errors)
    setApiError(null)
    setAnalysis(null)

    if (Object.keys(errors).length > 0) return
    if (isEditing && projectStatus === 'PUBLISHED') {
      setApiError('Un projet publié ne peut plus être modifié.')
      return
    }
    if (isEditing && projectStatus === 'ANALYZED' && !window.confirm(
      'Modifier ce projet remettra son statut en brouillon et supprimera la validité de son analyse. Continuer ?',
    )) return

    setIsAnalyzing(true)
    try {
      const payload: ProjectInput = {
        name: values.name.trim(),
        description: values.description.trim(),
        deadline: values.deadline,
        estimated_amount: values.amount.trim().replace(',', '.'),
      }
      const project = isEditing && editingProjectId !== null
        ? await updateProject(editingProjectId, payload)
        : await createProject(payload)
      setProjectId(project.id)
      setProjectStatus(project.status)

      if (isEditing) {
        navigate('/projects', { state: { successMessage: 'Projet modifié avec succès.' } })
        return
      }

      const response = await analyzeWithTimeout(project.id)
      setAnalysis(response)
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === 400) {
        const data = error.data
        let hasFieldError = false
        if (typeof data === 'object' && data !== null) {
          const fieldMap: Record<string, keyof FormValues> = {
            name: 'name',
            description: 'description',
            deadline: 'deadline',
            estimated_amount: 'amount',
          }
          Object.entries(data).forEach(([field, message]) => {
            const formField = fieldMap[field]
            if (formField) {
              const messages = Array.isArray(message) ? message : [message]
              const messageText = messages.filter((item): item is string => typeof item === 'string').join(' ')
              if (messageText) {
                hasFieldError = true
                setFormErrors((current) => ({ ...current, [formField]: messageText }))
              }
            }
          })
        }
        setApiError(hasFieldError ? null : error.message)
      } else if (error instanceof ApiError && error.code === 429) {
        setApiError('Trop d’analyses, réessayez plus tard.')
      } else if (error instanceof Error && error.message === 'ANALYSIS_TIMEOUT') {
        setApiError('L’analyse prend plus de temps que prévu. Vous pouvez réessayer.')
      } else if (error instanceof Error) {
        setApiError(error.message)
      } else {
        setApiError('Une erreur est survenue. Veuillez réessayer.')
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  const retryAnalysis = () => {
    if (projectId === null) return
    setApiError(null)
    setIsAnalyzing(true)
    void analyzeWithTimeout(projectId)
      .then(setAnalysis)
      .catch((error: unknown) => {
        setApiError(
          error instanceof ApiError && error.code === 429
            ? 'Trop d’analyses, réessayez plus tard.'
            : error instanceof Error ? error.message : 'Une erreur est survenue. Veuillez réessayer.',
        )
      })
      .finally(() => setIsAnalyzing(false))
  }

  const finalizeProject = async (publish: boolean) => {
    if (projectId === null) return

    setIsFinalizing(true)
    setApiError(null)
    try {
      if (publish) {
        await publishProject(projectId)
        navigate('/gestion-projets', { state: { successMessage: 'Projet publié avec succès.' } })
      } else {
        await declineProject(projectId)
        setProjectStatus('DECLINED')
        setApiError('Projet refusé')
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === 409) {
        try {
          const project = await getProject(projectId)
          setValues({
            name: project.name,
            description: project.description,
            deadline: project.deadline,
            amount: project.estimated_amount,
          })
          setProjectStatus(project.status)
          setAnalysis(null)
          setApiError('Ce projet n’est plus dans un état qui permet cette action.')
        } catch (reloadError: unknown) {
          setApiError(reloadError instanceof Error ? reloadError.message : 'Impossible de recharger le projet.')
        }
      } else if (error instanceof ApiError && error.code === 429) {
        setApiError('Trop d’analyses, réessayez plus tard.')
      } else {
        setApiError(error instanceof Error ? error.message : 'Une erreur est survenue. Veuillez réessayer.')
      }
    } finally {
      setIsFinalizing(false)
    }
  }

  const result = analysis?.result
  const amount = Number(values.amount.replace(',', '.'))
  const confidence = result ? percentage(result.confiance) : 0
  const successRate = result ? percentage(result.taux_reussite) : 0
  const budgetMin = result?.budget_min
  const budgetMax = result?.budget_max
  const hasBudgetRange = Number.isFinite(budgetMin) && Number.isFinite(budgetMax)
  const budgetScaleMax = hasBudgetRange
    ? Math.max(budgetMax ?? 0, Number.isFinite(amount) ? amount : 0, budgetMin ?? 0)
    : 0
  const budgetStart = hasBudgetRange && budgetScaleMax > 0 ? ((budgetMin ?? 0) / budgetScaleMax) * 100 : 0
  const budgetEnd = hasBudgetRange && budgetScaleMax > 0 ? ((budgetMax ?? 0) / budgetScaleMax) * 100 : 0
  const estimatedAmountPosition = hasBudgetRange && budgetScaleMax > 0 && Number.isFinite(amount)
    ? Math.min(100, Math.max(0, (amount / budgetScaleMax) * 100))
    : null
  const deadlineDate = values.deadline ? new Date(`${values.deadline}T00:00:00`) : null
  const remainingDays = deadlineDate && !Number.isNaN(deadlineDate.getTime())
    ? Math.ceil((deadlineDate.getTime() - today.getTime()) / 86_400_000)
    : null
  const budgetLabel = result
    ? result.coherence_budget === 'REALISTE'
      ? 'Budget réaliste'
      : result.coherence_budget === 'SOUS_ESTIME'
        ? 'Budget sous-estimé'
        : result.coherence_budget === 'SUR_ESTIME'
          ? 'Budget surestimé'
          : amount < result.budget_min
            ? 'Budget sous-estimé'
            : amount > result.budget_max
              ? 'Budget surestimé'
              : 'À vérifier'
    : null

  return (
    <main className="page-shell">
      <section className="card page-card">
        <div className="auth-heading">
          <div className="auth-icon"><Sparkles aria-hidden="true" size={26} /></div>
          <h1>{isEditing ? 'Modifier le projet' : 'Nouveau projet'}</h1>
          <p>Décrivez votre besoin pour obtenir une analyse assistée par IA.</p>
        </div>

        {apiError && !analysis?.error && <p className="alert alert-error" role="alert">{apiError}</p>}

        {isLoadingProject ? <p className="loading-state"><Loader2 className="spin" aria-hidden="true" size={18} /> Chargement du projet...</p> : <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="project-name">Nom du projet</label>
            <input className="form-input" id="project-name" maxLength={150} value={values.name} onChange={(event) => updateValue('name', event.target.value)} />
            {formErrors.name && <small className="field-error">{formErrors.name}</small>}
          </div>
          <div className="form-group">
            <label htmlFor="project-description">Description</label>
            <textarea className="form-input" id="project-description" maxLength={3000} rows={6} value={values.description} onChange={(event) => updateValue('description', event.target.value)} />
            {formErrors.description && <small className="field-error">{formErrors.description}</small>}
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="project-deadline">Date limite</label>
              <input className="form-input" id="project-deadline" type="date" value={values.deadline} onChange={(event) => updateValue('deadline', event.target.value)} />
              {formErrors.deadline && <small className="field-error">{formErrors.deadline}</small>}
            </div>
            <div className="form-group">
              <label htmlFor="project-amount">Montant estimé (€)</label>
              <input className="form-input" id="project-amount" min="0.01" step="0.01" inputMode="decimal" type="text" value={values.amount} onChange={(event) => updateValue('amount', event.target.value.replace(',', '.'))} />
              {formErrors.amount && <small className="field-error">{formErrors.amount}</small>}
            </div>
          </div>
          <button className="btn btn-primary form-submit" type="submit" disabled={isAnalyzing || isFinalizing}>
            {isAnalyzing
              ? <><Loader2 className="spin" aria-hidden="true" size={18} />{isEditing ? 'Enregistrement...' : 'Analyse en cours...'}</>
              : isEditing ? 'Enregistrer les modifications' : 'Analyser avec l’IA'}
          </button>
        </form>
        }
      </section>

      {isAnalyzing && (
        <section className="card page-card" aria-live="polite">
          <div className="loading-state" aria-busy="true">
            <Loader2 className="spin" aria-hidden="true" size={20} />
            <p>Analyse en cours, cela peut prendre jusqu’à une minute...</p>
            <div style={{ height: '0.8rem', margin: '0.75rem auto', maxWidth: '32rem', background: '#e8e6f7', borderRadius: '999px' }} />
            <div style={{ height: '0.8rem', margin: '0.75rem auto', maxWidth: '24rem', background: '#e8e6f7', borderRadius: '999px' }} />
          </div>
        </section>
      )}

      {analysis?.error && (
        <section className="card page-card" aria-live="polite">
          <div className="alert alert-error" role="alert">
            <strong>Analyse indisponible, réessayez plus tard.</strong>
            <button className="btn btn-secondary" type="button" onClick={retryAnalysis} disabled={isAnalyzing}>Réessayer</button>
          </div>
        </section>
      )}

      {analysis && !analysis.error && !analysis.result && (
        <section className="card page-card" aria-live="polite">
          <div className="alert alert-error" role="alert">
            <strong>Analyse indisponible, réessayez plus tard.</strong>
            <button className="btn btn-secondary" type="button" onClick={retryAnalysis} disabled={isAnalyzing}>Réessayer</button>
          </div>
        </section>
      )}

      {analysis && !analysis.error && result && (
        <section className="card page-card" aria-live="polite">
          {analysis.simulated && (
            <div className="alert alert-warning" role="status" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#fff4d6' }}>
              <Sparkles aria-hidden="true" size={18} />
              <strong>Analyse simulée</strong>
            </div>
          )}
          <div className="profile-heading">
            <div>
              <h2>Résultat de l’analyse</h2>
              <p>Une synthèse pour vous aider à prendre votre décision.</p>
            </div>
            {result.complexite && <span className={`badge ${complexityClass(result.complexite)}`}>Complexité : {complexityLabel(result.complexite)}{Number.isFinite(result.score_complexite) ? ` · ${result.score_complexite}/10` : ''}</span>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
            {Number.isFinite(result.duree_semaines) && (
              <div className="analysis-panel"><Clock3 aria-hidden="true" size={20} /><strong>Durée</strong><p style={{ fontSize: '1.8rem', margin: '0.25rem 0' }}>{result.duree_semaines}</p><span>semaines</span>{Number.isFinite(result.duree_min_semaines) && Number.isFinite(result.duree_max_semaines) && <small>{result.duree_min_semaines} à {result.duree_max_semaines} semaines</small>}</div>
            )}
            {Number.isFinite(result.nb_freelancers) && (
              <div className="analysis-panel"><Users aria-hidden="true" size={20} /><strong>Équipe</strong><p style={{ fontSize: '1.8rem', margin: '0.25rem 0' }}>{result.nb_freelancers}</p><span>freelancer{result.nb_freelancers > 1 ? 's' : ''}</span></div>
            )}
            {hasBudgetRange && (
              <div className="analysis-panel"><strong>Budget recommandé</strong><p>{formatAmount(budgetMin ?? NaN)} – {formatAmount(budgetMax ?? NaN)}</p></div>
            )}
            {Number.isFinite(result.confiance) && (
              <div className="analysis-panel"><strong>Confiance de l’IA</strong><p>{confidence}% <span title="confiance de l’IA dans son analyse, pas une garantie" aria-label="confiance de l’IA dans son analyse, pas une garantie"><Info aria-hidden="true" size={16} /></span></p><progress max={100} value={Math.min(100, Math.max(0, confidence))} aria-label="Confiance de l’IA" aria-valuemin={0} aria-valuemax={100} aria-valuenow={confidence} /></div>
            )}
          </div>
          {hasBudgetRange && (
            <div className="analysis-panel">
              <h3>Budget</h3>
              <div role="img" aria-label={`Fourchette recommandée de ${formatAmount(budgetMin ?? NaN)} à ${formatAmount(budgetMax ?? NaN)} et montant estimé de ${formatAmount(amount)}`} style={{ position: 'relative', height: '2rem', margin: '1rem 0' }}>
                <div style={{ position: 'absolute', top: '0.7rem', width: '100%', height: '0.6rem', background: '#e5e7eb', borderRadius: '999px' }} />
                <div style={{ position: 'absolute', top: '0.55rem', left: `${budgetStart}%`, width: `${Math.max(2, budgetEnd - budgetStart)}%`, height: '0.9rem', background: '#6d5bd0', borderRadius: '999px' }} />
                {estimatedAmountPosition !== null && <span style={{ position: 'absolute', top: 0, left: `${estimatedAmountPosition}%`, width: '3px', height: '2rem', background: '#222', transform: 'translateX(-50%)' }} />}
              </div>
              <p><strong>Montant estimé :</strong> {formatAmount(amount)}</p>
              {budgetLabel && <p><span className="badge badge-neutral"><CircleAlert aria-hidden="true" size={15} /> {budgetLabel}</span></p>}
              {result.justification && <p>{result.justification}</p>}
            </div>
          )}
          {result.faisabilite_deadline && (
            <div className="analysis-panel">
              <h3><CalendarClock aria-hidden="true" size={20} /> Deadline</h3>
              <p><span className="badge badge-neutral">{result.faisabilite_deadline === 'TENABLE' ? 'Tenable' : result.faisabilite_deadline === 'SERREE' ? 'Serrée' : result.faisabilite_deadline === 'IRREALISTE' ? 'Irréaliste' : result.faisabilite_deadline}</span></p>
              {remainingDays !== null && <p><strong>Jours restants :</strong> {remainingDays}</p>}
              {result.faisabilite_deadline_justification && <p>{result.faisabilite_deadline_justification}</p>}
            </div>
          )}
          {Number.isFinite(result.taux_reussite) && (
            <div className="analysis-panel">
              <h3>Indice de réussite</h3>
              <p>{successRate}%</p>
              <progress max={100} value={Math.min(100, Math.max(0, successRate))} aria-label="Indice de réussite estimé" aria-valuemin={0} aria-valuemax={100} aria-valuenow={successRate} />
              <small>Estimation qualitative, pas une probabilité.</small>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <div><strong>Facteurs positifs</strong>{Array.isArray(result.facteurs_positifs) && <ul>{result.facteurs_positifs.map((factor, index) => <li key={`${factor}-${index}`}>{factor}</li>)}</ul>}</div>
                <div><strong>Facteurs négatifs</strong>{Array.isArray(result.facteurs_negatifs) && <ul>{result.facteurs_negatifs.map((factor, index) => <li key={`${factor}-${index}`}>{factor}</li>)}</ul>}</div>
              </div>
            </div>
          )}
          {result.recommandation && <div className="alert alert-info"><strong>Recommandation</strong><p>{result.recommandation}</p></div>}
          {Array.isArray(result.specialites) && result.specialites.length > 0 && (
            <details open>
              <summary><strong>Spécialités recommandées</strong></summary>
              <div className="form-row">
                {result.specialites.map((specialite, index) => (
                  <span className="badge badge-neutral" key={`${specialite.nom}-${index}`}>
                    {specialite.nom} : {specialite.nb} personne{specialite.nb > 1 ? 's' : ''}{specialite.niveau ? ` · Niveau ${specialite.niveau}` : ''}{Number.isFinite(specialite.charge_pourcentage) ? ` · ${specialite.charge_pourcentage}%` : ''}
                  </span>
                ))}
              </div>
            </details>
          )}
          {Array.isArray(result.risques) && result.risques.length > 0 && (
            <details>
              <summary><strong>Risques</strong></summary>
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {[...result.risques].sort((a, b) => riskSeverity(b) - riskSeverity(a)).map((risk, index) => (
                  <article className="analysis-panel" key={`${risk.description}-${index}`}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                      <AlertTriangle aria-hidden="true" size={18} />
                      <strong>{risk.description}</strong>
                    </div>
                    <div className="form-row">
                      <span className="badge badge-suspect">Probabilité : {Number.isFinite(risk.probabilite) ? `${Math.round(percentage(risk.probabilite))}%` : 'Non renseignée'}</span>
                      <span className="badge badge-rejete">Impact : {risk.impact ? frenchLevel(risk.impact) : 'Non renseigné'}</span>
                    </div>
                    {risk.mitigation && <p><strong>Mesure :</strong> {risk.mitigation}</p>}
                  </article>
                ))}
              </div>
            </details>
          )}
          {Array.isArray(result.jalons) && result.jalons.length > 0 && (
            <details open>
              <summary><strong>Jalons</strong></summary>
              <ol style={{ display: 'grid', gap: '0.75rem', paddingLeft: '1.5rem' }}>{result.jalons.map((milestone, index) => (
                <li key={`${milestone.nom}-${index}`}><strong>Semaine {milestone.semaine}</strong> — {milestone.nom} <CheckCircle2 aria-hidden="true" size={16} /></li>
              ))}</ol>
            </details>
          )}
          {Array.isArray(result.phases) && result.phases.length > 0 && (
            <>
              <div className="analysis-panel">
                <h3>Frise des phases</h3>
                <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'stretch', minHeight: '3rem' }} aria-label="Durée relative des phases">
                  {result.phases.map((phase, index) => (
                    <div key={`${phase.nom}-timeline-${index}`} title={`${phase.nom} : ${phase.duree_semaines} semaine${phase.duree_semaines > 1 ? 's' : ''}`} style={{ flex: Math.max(1, phase.duree_semaines), padding: '0.5rem', color: '#fff', background: index % 2 === 0 ? '#6d5bd0' : '#4c8dca', borderRadius: '0.35rem', overflow: 'hidden' }}>
                      <strong>{phase.nom}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <details>
                <summary><strong>Détails des phases</strong></summary>
              {result.phases.map((phase, index) => (
                <article className="analysis-panel" key={`${phase.nom}-${index}`}>
                  <h3>{phase.nom}</h3>
                  {phase.objectif && <p>{phase.objectif}</p>}
                  <p><strong>Durée :</strong> {phase.duree_semaines} semaine{phase.duree_semaines > 1 ? 's' : ''} · <strong>Budget :</strong> {phase.budget_pourcentage}%</p>
                  {Array.isArray(phase.livrables) && phase.livrables.length > 0 && <div><strong>Livrables :</strong><div className="form-row">{phase.livrables.map((item, itemIndex) => <span className="badge badge-neutral" key={`${item}-${itemIndex}`}>{item}</span>)}</div></div>}
                  {Array.isArray(phase.specialites) && phase.specialites.length > 0 && <div><strong>Spécialités :</strong><div className="form-row">{phase.specialites.map((item, itemIndex) => <span className="badge badge-neutral" key={`${item}-${itemIndex}`}>{item}</span>)}</div></div>}
                </article>
              ))}
              </details>
            </>
          )}
          {Array.isArray(result.hypotheses) && result.hypotheses.length > 0 && (
            <details><summary><strong>Hypothèses</strong></summary><ul>{result.hypotheses.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></details>
          )}
          {Array.isArray(result.questions_clarification) && result.questions_clarification.length > 0 && (
            <details><summary><strong>Questions de clarification</strong></summary><ul>{result.questions_clarification.map((item, index) => <li key={`${item}-${index}`}><span className="badge badge-suspect">À préciser</span> {item}</li>)}</ul></details>
          )}
          {Array.isArray(result.recommandations) && result.recommandations.length > 0 && (
            <div className="analysis-panel"><h3>Recommandations</h3><ul>{result.recommandations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div>
          )}
          {Array.isArray(result.references_used) && result.references_used.length > 0 && (
            <footer style={{ marginTop: '1.5rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
              <strong>Références utilisées</strong>
              <ul>{result.references_used.map((reference, index) => <li key={`${reference}-${index}`}>{reference}</li>)}</ul>
            </footer>
          )}
          {projectId !== null && (
            <div className="detail-actions">
              <p className="decision-note">L’IA aide à décider, vous décidez.</p>
              <button className="btn btn-primary" type="button" onClick={() => void finalizeProject(true)} disabled={isFinalizing}>{isFinalizing ? 'Traitement...' : 'Accepter la publication'}</button>
              <button className="btn btn-secondary" type="button" onClick={() => void finalizeProject(false)} disabled={isFinalizing}>Refuser</button>
            </div>
          )}
        </section>
      )}
    </main>
  )
}

export default NewProjectPage
