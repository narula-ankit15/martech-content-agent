import { useEffect, useState } from "react";
import { getInsights } from "../api";
import EmailInsightsPanel from "./EmailInsightsPanel";
import WhatsAppInsightsPanel from "./WhatsAppInsightsPanel";
import IllustrativeBenchmarks from "./IllustrativeBenchmarks";
import ArchitectureModal from "./ArchitectureModal";

export default function HomePage({ projects, projectId, onProjectIdChange, onGoBrowse, onGoCreate }) {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showArchitecture, setShowArchitecture] = useState(false);

  useEffect(() => {
    if (!projectId.trim()) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getInsights(projectId.trim())
      .then((data) => {
        if (!cancelled) setInsights(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <div className="home">
      <section className="home__hero">
        <h2 className="home__hero-title">Marketing Content Studio</h2>
        <p className="home__hero-subtitle">
          Generate on-brand email and WhatsApp content, backed by a multi-agent system that pulls from your
          project's real facts, brochures, and asset bank.
        </p>
        <div className="home__hero-actions">
          <button className="btn btn--cta home__hero-btn" onClick={onGoCreate}>
            + Create New Content
          </button>
          <button className="btn btn--ghost home__hero-btn" onClick={onGoBrowse}>
            Browse Library
          </button>
        </div>
      </section>

      <section className="home__insights">
        <div className="home__insights-header">
          <h3>Content Insights</h3>
          <select
            className="filter-bar__input home__insights-project"
            value={projectId}
            onChange={(e) => onProjectIdChange(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.project_name}
              </option>
            ))}
          </select>
        </div>
        <p className="home__insights-hint">
          What kind of content you've actually been creating in this project's library — length, wording,
          imagery, and CTA patterns. This app doesn't track sends or opens, so this is composition, not
          performance (see the illustrative example further down for what performance benchmarks could look
          like).
        </p>

        {loading && <div className="state-message">Loading insights&hellip;</div>}
        {error && <div className="state-message state-message--error">{error}</div>}

        {insights && !loading && !error && (
          <>
            <div className="insights-grid">
              <EmailInsightsPanel data={insights.email} />
              <WhatsAppInsightsPanel data={insights.whatsapp} />
            </div>
            <IllustrativeBenchmarks />
          </>
        )}
      </section>

      <button className="home__architecture-btn" onClick={() => setShowArchitecture(true)}>
        <span className="home__architecture-icon">?</span>
        How this content system works
      </button>

      {showArchitecture && <ArchitectureModal onClose={() => setShowArchitecture(false)} />}
    </div>
  );
}
