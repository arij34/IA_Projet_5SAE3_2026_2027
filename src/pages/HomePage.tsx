import {
  ArrowUp,
  BookOpen,
  CalendarCheck,
  Check,
  Calculator,
  Network,
  Rocket,
  ShieldCheck,
  Sparkles,
  Trophy,
  UserPlus,
} from 'lucide-react'
import { type CSSProperties, type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getToken } from '../auth/tokenStorage'
import { useReveal } from '../hooks/useReveal'

type HomeCard = {
  title: string
  description: string
  icon: typeof ShieldCheck
  iconClass: string
}

const benefits: HomeCard[] = [
  { title: 'Profils vérifiés', description: 'La détection des faux profils par IA renforce la confiance dès le départ.', icon: ShieldCheck, iconClass: 'icon-green' },
  { title: 'Profils optimisés', description: 'Des suggestions d’amélioration par IA vous aident à mieux présenter votre profil.', icon: Sparkles, iconClass: 'icon-purple' },
  { title: 'Matching intelligent', description: 'Trouvez plus facilement les compétences et les projets qui correspondent à vos besoins.', icon: Network, iconClass: 'icon-blue' },
  { title: 'Analyse de projet', description: 'Obtenez une meilleure visibilité sur la durée, le budget et les enjeux de votre projet.', icon: Calculator, iconClass: 'icon-orange' },
  { title: 'Challenges', description: 'Mettez vos compétences en pratique et relevez de nouveaux défis professionnels.', icon: Trophy, iconClass: 'icon-pink' },
  { title: 'Blog', description: 'Retrouvez des conseils et des ressources pour progresser dans vos collaborations.', icon: BookOpen, iconClass: 'icon-teal' },
]

type Step = HomeCard

const steps: Step[] = [
  { title: 'Créez votre profil', description: 'Présentez vos compétences et vos ambitions.', icon: UserPlus, iconClass: 'icon-blue' },
  { title: 'L’IA et un administrateur vérifient votre profil', description: 'Chaque profil est analysé puis vérifié.', icon: ShieldCheck, iconClass: 'icon-green' },
  { title: 'Trouvez le bon partenaire grâce au matching intelligent', description: 'Identifiez les projets et talents qui vous correspondent.', icon: Network, iconClass: 'icon-purple' },
  { title: 'Planifiez votre projet', description: 'Organisez le planning du projet et des tâches.', icon: CalendarCheck, iconClass: 'icon-orange' },
  { title: 'Participez aux challenges pour valoriser vos compétences', description: 'Relevez des défis et faites grandir votre expérience.', icon: Trophy, iconClass: 'icon-pink' },
]

function RevealSection({ children, className = '' }: { children: ReactNode; className?: string }) {
  const [ref, isVisible] = useReveal<HTMLElement>()
  return <section ref={ref} className={`reveal ${isVisible ? 'is-visible' : ''} ${className}`}>{children}</section>
}

function HomePage() {
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [stepsRef, stepsVisible] = useReveal<HTMLDivElement>()
  const isAuthenticated = Boolean(getToken())

  useEffect(() => {
    const handleScroll = () => setShowBackToTop(window.scrollY > 400)
    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <>
      <section className="hero">
        <div className="hero-orb orb-one" />
        <div className="hero-orb orb-two" />
        <div className="hero-orb orb-three" />
        <div className="container hero-content">
          <p className="eyebrow hero-item">La confiance au cœur des collaborations</p>
          <h1 className="hero-item">Trouvez le bon talent, en toute confiance</h1>
          <p className="hero-lead hero-item">Freelancy est la plateforme propulsée par l’IA qui connecte les porteurs de projet et les freelances, avec des profils vérifiés et des collaborations plus sereines.</p>
        </div>
      </section>

      <RevealSection className="section">
        <div className="container">
          <div className="section-heading">
            <p className="eyebrow">Une plateforme plus intelligente</p>
            <h2>Pourquoi Freelancy ?</h2>
            <p>Des outils pensés pour simplifier les rencontres professionnelles et construire la confiance.</p>
          </div>
          <div className="benefits-grid">
            {benefits.map(({ title, description, icon: Icon, iconClass }, index) => (
              <article className="card reveal-card" style={{ '--reveal-delay': `${index * 70}ms` } as CSSProperties} key={title}>
                <div className={`feature-icon ${iconClass}`}><Icon aria-hidden="true" size={24} /></div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </div>
      </RevealSection>

      <RevealSection className="section">
        <div className="container">
          <div className="section-heading">
            <p className="eyebrow">Un parcours simple</p>
            <h2>Comment ça marche</h2>
            <p>De votre inscription à votre prochaine collaboration, Freelancy vous accompagne à chaque étape.</p>
          </div>
          <div className={`steps-grid progress-steps ${stepsVisible ? 'is-visible' : ''}`} ref={stepsRef}>
            <div className="progress-line" aria-hidden="true"><span /></div>
            {steps.map(({ title, description, icon: Icon, iconClass }, index) => (
              <article className="card step-card" style={{ '--reveal-delay': `${index * 120}ms` } as CSSProperties} key={title}>
                <span className="step-number">{index + 1}</span>
                <div className={`step-icon ${iconClass}`}><Icon aria-hidden="true" size={22} /></div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </div>
      </RevealSection>

      <RevealSection className="container cta">
        <div className="cta-orb cta-orb-one" />
        <div className="cta-orb cta-orb-two" />
        <div className="cta-content">
          <div className="cta-icon"><Rocket aria-hidden="true" size={26} /></div>
          <p className="cta-eyebrow">Votre prochaine étape</p>
          <h2>Prêt à lancer votre prochaine collaboration ?</h2>
          <p>Rejoignez Freelancy pour trouver les bonnes compétences, structurer vos projets et avancer avec confiance.</p>
          <div className="cta-actions">
            {isAuthenticated ? (
              <Link className="btn btn-cta-primary" to="/profile">Accéder à mon profil</Link>
            ) : (
              <>
                <Link className="btn btn-cta-primary" to="/register">Créer un compte</Link>
                <Link className="btn btn-cta-outline" to="/login">Se connecter</Link>
              </>
            )}
          </div>
          <div className="cta-points">
            <span><Check aria-hidden="true" size={16} />Profils vérifiés</span>
            <span><Check aria-hidden="true" size={16} />Matching intelligent</span>
            <span><Check aria-hidden="true" size={16} />Inscription gratuite</span>
          </div>
        </div>
      </RevealSection>

      <button className={`back-to-top${showBackToTop ? ' is-visible' : ''}`} type="button" aria-label="Retour en haut" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
        <ArrowUp aria-hidden="true" size={20} />
      </button>
    </>
  )
}

export default HomePage
