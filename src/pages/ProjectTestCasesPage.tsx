import { useState } from 'react'
import { ArrowLeft, CheckSquare, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { generateProjectTestCases, type TestCaseGenerationResponse } from '../api/testCases'
import './ProjectTestCasesPage.css'

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.data === 'object' && error.data !== null && 'code' in error.data) {
      const code = String(error.data.code)
      if (code === 'provider_not_configured') return 'Le service Mistral n’est pas configuré sur le serveur.'
      if (code === 'provider_rate_limited') return 'Mistral a temporairement limité cette requête. Vérifiez les limites d’utilisation de votre compte Mistral ou réessayez plus tard.'
      if (code === 'provider_timeout') return 'Mistral met trop de temps à répondre. Vous pouvez réessayer.'
    }
    if (error.status === 429) return 'La limite de générations de Freelancy est atteinte. Réessayez plus tard.'
    if (error.status === 404) return 'Projet introuvable ou accès refusé.'
    return 'La génération a échoué. Vérifiez le descriptif du projet puis réessayez.'
  }
  return error instanceof Error ? error.message : 'Une erreur inattendue est survenue.'
}

function ProjectTestCasesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const parsedId = Number(projectId)
  const validId = Number.isInteger(parsedId) && parsedId > 0
  const [result, setResult] = useState<TestCaseGenerationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleGenerate = async () => {
    if (!validId || isLoading) return
    setError(null)
    setIsLoading(true)
    try {
      setResult(await generateProjectTestCases(parsedId))
    } catch (reason: unknown) {
      setError(errorText(reason))
      setResult(null)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="page-shell">
      <section className="card page-card qa-page">
        <Link className="qa-back-link" to="/gestion-projets"><ArrowLeft aria-hidden="true" size={17} /> Mes projets</Link>
        <div className="auth-heading">
          <div className="auth-icon"><CheckSquare aria-hidden="true" size={25} /></div>
          <h1>Cas de test du projet</h1>
          <p>Générez des scénarios QA vérifiables à partir du descriptif enregistré de votre projet.</p>
        </div>
        {!validId && <p className="alert alert-error" role="alert">Identifiant de projet invalide.</p>}
        <div className="qa-action">
          <p>Le serveur transmet à Mistral le nom et le descriptif de ce projet après anonymisation des coordonnées courantes.</p>
          <button className="btn btn-primary" type="button" onClick={() => void handleGenerate()} disabled={!validId || isLoading}>
            {isLoading
              ? <><Loader2 className="spin" aria-hidden="true" size={18} /> Génération en cours…</>
              : <><Sparkles aria-hidden="true" size={17} /> {result ? 'Régénérer les cas' : 'Générer les cas de test'}</>}
          </button>
        </div>
        {error && <div className="alert alert-error" role="alert">{error}<button className="btn btn-secondary" type="button" onClick={() => void handleGenerate()} disabled={isLoading}><RefreshCw aria-hidden="true" size={15} /> Réessayer</button></div>}
        {result && (
          <section aria-live="polite" className="qa-results">
            <div className="qa-results-heading">
              <div><h2>{result.project_name}</h2><p>{result.test_cases.length} cas proposés par {result.provider} · {result.model}</p></div>
            </div>
            <div className="qa-case-list">
              {result.test_cases.map((testCase, index) => (
                <article className="card qa-case" key={`${index}-${testCase.title}`}>
                  <div className="qa-case-heading">
                    <h3>{index + 1}. {testCase.title}</h3>
                    <span className={`badge qa-priority qa-priority-${testCase.priority}`}>{testCase.priority}</span>
                  </div>
                  <p><strong>Exigence visée :</strong> {testCase.requirement}</p>
                  <p><strong>Catégorie :</strong> {testCase.category}</p>
                  {testCase.preconditions.length > 0 && <><h4>Préconditions</h4><ul>{testCase.preconditions.map((item, i) => <li key={`${i}-${item}`}>{item}</li>)}</ul></>}
                  <h4>Étapes</h4>
                  <ol>{testCase.steps.map((step, i) => <li key={`${i}-${step}`}>{step}</li>)}</ol>
                  <p className="qa-expected"><strong>Résultat attendu :</strong> {testCase.expected_result}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  )
}

export default ProjectTestCasesPage
