import { type ChangeEvent, type FormEvent, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { analyzeProfile, ApiError, ApiTimeoutError, type ProfileAnalysisResponse } from '../api/client'
import type { ProfileUpdate } from '../types'

type FreelancerProfileFormProps = {
  initialValue: ProfileUpdate
  currentCvUrl: string | null
  isSubmitting: boolean
  onSubmit: (value: ProfileUpdate) => void
}

const MAX_CV_SIZE = 5 * 1024 * 1024

function getSkills(value: string): string[] {
  return value.split(',').map((skill) => skill.trim()).filter((skill) => skill.length > 0)
}

function FreelancerProfileForm({
  initialValue,
  currentCvUrl,
  isSubmitting,
  onSubmit,
}: FreelancerProfileFormProps) {
  const [title, setTitle] = useState(initialValue.title)
  const [bio, setBio] = useState(initialValue.bio)
  const [skills, setSkills] = useState(initialValue.skills.join(', '))
  const [hourlyRate, setHourlyRate] = useState(
    initialValue.hourly_rate === null ? '' : String(initialValue.hourly_rate),
  )
  const [cv, setCv] = useState<File | null>(initialValue.cv)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [analysis, setAnalysis] = useState<ProfileAnalysisResponse | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleCvChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    if (file !== null && (file.type !== 'application/pdf' || !file.name.toLowerCase().endsWith('.pdf'))) {
      event.target.value = ''
      setCv(null)
      setErrors((current) => ({ ...current, cv: 'Le CV doit être au format PDF.' }))
      return
    }
    if (file !== null && file.size > MAX_CV_SIZE) {
      event.target.value = ''
      setCv(null)
      setErrors((current) => ({ ...current, cv: 'Le CV ne doit pas dépasser 5 Mo.' }))
      return
    }
    setCv(file)
    setErrors((current) => ({ ...current, cv: '' }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors: Record<string, string> = {}
    const trimmedTitle = title.trim()
    const trimmedBio = bio.trim()
    const parsedSkills = getSkills(skills)
    const parsedHourlyRate = hourlyRate.trim() === '' ? null : Number(hourlyRate)
    if (!trimmedTitle) nextErrors.title = 'Le titre professionnel est obligatoire.'
    if (!trimmedBio) nextErrors.bio = 'La présentation est obligatoire.'
    if (parsedSkills.length === 0) nextErrors.skills = 'Ajoutez au moins une compétence.'
    if (parsedHourlyRate !== null && (!Number.isFinite(parsedHourlyRate) || parsedHourlyRate < 0)) {
      nextErrors.hourly_rate = 'Le tarif horaire doit être un nombre positif ou nul.'
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    onSubmit({ title: trimmedTitle, bio: trimmedBio, skills: parsedSkills, hourly_rate: parsedHourlyRate, cv })
  }

  const handleAnalysis = async () => {
    setAnalysisError(null)
    setAnalysis(null)
    setIsAnalyzing(true)
    try {
      const result = await analyzeProfile({
        title,
        bio,
        skills,
        hourly_rate: hourlyRate,
      })
      setAnalysis(result)
    } catch (error: unknown) {
      if (error instanceof ApiTimeoutError) {
        setAnalysisError('L’analyse a pris trop de temps. Veuillez réessayer.')
      } else if (error instanceof ApiError) {
        if (error.status === 401) setAnalysisError('Votre session a expiré. Veuillez vous reconnecter.')
        else if (error.status === 403) setAnalysisError('Seuls les freelancers approuvés peuvent utiliser cette fonctionnalité.')
        else if (error.status === 400) setAnalysisError(getAnalysisErrorMessage(error.data))
        else setAnalysisError('Une erreur est survenue pendant l’analyse. Veuillez réessayer.')
      } else if (error instanceof Error) {
        setAnalysisError(error.message)
      } else {
        setAnalysisError('Le réseau est indisponible. Vérifiez votre connexion puis réessayez.')
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  const tags = getSkills(skills)

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="title">Titre professionnel</label>
        <input className="form-input" id="title" name="title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={120} />
        {errors.title && <p className="form-error" role="alert">{errors.title}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="bio">Présentation</label>
        <textarea className="form-input" id="bio" name="bio" value={bio} onChange={(event) => setBio(event.target.value)} />
        {errors.bio && <p className="form-error" role="alert">{errors.bio}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="skills">Compétences</label>
        <input className="form-input" id="skills" name="skills" value={skills} onChange={(event) => setSkills(event.target.value)} placeholder="Ex. React, UX, Python" />
        <small className="field-hint">Séparez les compétences par des virgules.</small>
        {tags.length > 0 && <div className="skill-tags" aria-label="Compétences sélectionnées">
          {tags.map((tag) => <span className="skill-tag" key={tag}>{tag}</span>)}
        </div>}
        {errors.skills && <p className="form-error" role="alert">{errors.skills}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="cv">Importer mon CV</label>
        {currentCvUrl && <a href={currentCvUrl} target="_blank" rel="noreferrer">Télécharger mon CV actuel</a>}
        <input className="form-input" id="cv" type="file" accept="application/pdf,.pdf" onChange={handleCvChange} />
        {cv && <div className="file-selection"><span>{cv.name}</span><button className="btn btn-secondary" type="button" onClick={() => setCv(null)}>Retirer</button></div>}
        <small className="field-hint">PDF uniquement, 5 Mo maximum.</small>
        {errors.cv && <p className="form-error" role="alert">{errors.cv}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="hourly_rate">Tarif horaire (€)</label>
        <input
          className="form-input"
          id="hourly_rate"
          name="hourly_rate"
          type="number"
          min="0"
          step="any"
          value={hourlyRate}
          onChange={(event) => setHourlyRate(event.target.value)}
          placeholder="Ex. 50"
        />
        {errors.hourly_rate && <p className="form-error" role="alert">{errors.hourly_rate}</p>}
      </div>
      <button className="btn btn-primary form-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? <><Loader2 className="spin" aria-hidden="true" size={18} />Enregistrement en cours...</> : 'Enregistrer'}
      </button>
      <section className="profile-analysis" aria-labelledby="profile-analysis-title">
        <div className="profile-analysis-heading">
          <div>
            <span className="profile-eyebrow">Diagnostic personnalisé</span>
            <h2 id="profile-analysis-title">Analyser mon profil</h2>
          </div>
          <button className="btn btn-secondary" type="button" onClick={() => void handleAnalysis()} disabled={isAnalyzing}>
            {isAnalyzing ? <><Loader2 className="spin" aria-hidden="true" size={18} />Analyser</> : 'Analyser mon profil'}
          </button>
        </div>
        {isAnalyzing && <p className="field-hint" role="status">Analyse en cours, cela peut prendre une minute</p>}
        {analysisError && <p className="alert alert-error" role="alert">{analysisError}</p>}
        {analysis && (
          <div className="profile-analysis-result" aria-live="polite">
            <div className="analysis-score">
              <div className="analysis-score-label"><strong>Score</strong><span>{analysis.score}/100</span></div>
              <div className="score-meter" role="progressbar" aria-label="Score du profil" aria-valuemin={0} aria-valuemax={100} aria-valuenow={analysis.score}>
                <span style={{ width: `${Math.max(0, Math.min(100, analysis.score))}%` }} />
              </div>
            </div>
            <p className="field-hint">Source : {analysis.source}</p>
            <div className="analysis-lists">
              <AnalysisList title="Points forts" items={analysis.points_forts} />
              <AnalysisList title="Points faibles" items={analysis.points_faibles} />
              <AnalysisList title="Suggestions" items={analysis.suggestions} />
            </div>
          </div>
        )}
      </section>
    </form>
  )
}

function getAnalysisErrorMessage(data: unknown): string {
  if (typeof data === 'object' && data !== null) {
    const messages = Object.entries(data as Record<string, unknown>).flatMap(([field, value]) => {
      if (typeof value === 'string' && value.trim()) return [`${field} : ${value}`]
      if (Array.isArray(value)) {
        return value
          .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
          .map((item) => `${field} : ${item}`)
      }
      return []
    })
    if (messages.length > 0) {
      return messages.join(' ; ')
    }
  }
  return 'Les informations du profil sont invalides.'
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3>{title}</h3>
      {items.length > 0 ? <ul>{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul> : <p className="field-hint">Aucun élément à signaler.</p>}
    </div>
  )
}

export default FreelancerProfileForm
