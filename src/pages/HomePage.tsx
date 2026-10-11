import { Link } from 'react-router-dom'

type HomeCard = {
  title: string
  description: string
}

const steps: HomeCard[] = [
  {
    title: 'Créez votre profil',
    description:
      'Présentez vos compétences, vos projets et vos ambitions en quelques minutes.',
  },
  {
    title: 'L’IA et un administrateur vérifient votre profil',
    description:
      'Chaque profil est analysé puis vérifié pour créer un environnement fiable.',
  },
  {
    title: 'Collaborez avec le bon partenaire',
    description:
      'Rencontrez le bon talent ou le bon projet pour construire ensemble.',
  },
]

const benefits: HomeCard[] = [
  {
    title: 'Profils vérifiés',
    description:
      'La détection des faux profils par IA renforce la confiance dès le départ.',
  },
  {
    title: 'Profils optimisés',
    description:
      'Des suggestions d’amélioration par IA vous aident à mieux présenter votre profil.',
  },
  {
    title: 'Matching intelligent',
    description:
      'Trouvez plus facilement les compétences et les projets qui correspondent à vos besoins.',
  },
  {
    title: 'Analyse de projet',
    description:
      'Obtenez une meilleure visibilité sur la durée, le budget et les enjeux de votre projet.',
  },
  {
    title: 'Challenges',
    description:
      'Mettez vos compétences en pratique et relevez de nouveaux défis professionnels.',
  },
  {
    title: 'Blog',
    description:
      'Retrouvez des conseils et des ressources pour progresser dans vos collaborations.',
  },
]

function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="container hero-content">
          <p className="eyebrow">La confiance au cœur des collaborations</p>
          <h1>Trouvez le bon talent, en toute confiance</h1>
          <p>
            Freelancy est la plateforme propulsée par l’IA qui connecte les
            porteurs de projet et les freelances, avec des profils vérifiés et
            des collaborations plus sereines.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/register">
              Créer un compte
            </Link>
            <Link className="btn btn-secondary" to="/login">
              Se connecter
            </Link>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="benefits-title">
        <div className="container">
          <div className="section-heading">
            <p className="eyebrow">Une plateforme plus intelligente</p>
            <h2 id="benefits-title">Pourquoi Freelancy ?</h2>
            <p>
              Des outils pensés pour simplifier les rencontres professionnelles
              et construire la confiance.
            </p>
          </div>
          <div className="benefits-grid">
            {benefits.map((benefit) => (
              <article className="card" key={benefit.title}>
                <h3>{benefit.title}</h3>
                <p>{benefit.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="how-it-works-title">
        <div className="container">
          <div className="section-heading">
            <p className="eyebrow">Un parcours simple</p>
            <h2 id="how-it-works-title">Comment ça marche</h2>
            <p>
              De votre inscription à votre prochaine collaboration, Freelancy
              vous accompagne à chaque étape.
            </p>
          </div>
          <div className="steps-grid">
            {steps.map((step, index) => (
              <article className="card" key={step.title}>
                <span className="step-number" aria-hidden="true">
                  {index + 1}
                </span>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="container cta" aria-labelledby="cta-title">
        <h2 id="cta-title">Prêt à commencer ?</h2>
        <p>
          Rejoignez une communauté de talents et de porteurs de projet qui
          avancent ensemble.
        </p>
        <Link className="btn btn-secondary" to="/register">
          Rejoindre Freelancy
        </Link>
      </section>
    </>
  )
}

export default HomePage
