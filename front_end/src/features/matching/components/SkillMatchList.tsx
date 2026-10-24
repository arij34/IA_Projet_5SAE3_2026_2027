interface Props {
  matched: string[]
  missing: string[]
  declared?: string[]
}

/** Liste les compétences couvertes et celles qui manquent au profil. */
function SkillMatchList({ matched, missing, declared }: Props) {
  return (
    <>
      {matched.length > 0 ? (
        <div className="skill-match-group">
          <h4>Compétences couvertes</h4>
          <div className="match-badges">
            {matched.map((skill) => (
              <span className="match-badge is-ok" key={`ok-${skill}`}>
                {skill}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {missing.length > 0 ? (
        <div className="skill-match-group">
          <h4>Compétences manquantes</h4>
          <div className="match-badges">
            {missing.map((skill) => (
              <span className="match-badge is-missing" key={`ko-${skill}`}>
                {skill}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {declared && declared.length > 0 ? (
        <div className="skill-match-group">
          <h4>Compétences déclarées</h4>
          <div className="match-badges">
            {declared.map((skill) => (
              <span className="match-badge" key={`declared-${skill}`}>
                {skill}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </>
  )
}

export default SkillMatchList
