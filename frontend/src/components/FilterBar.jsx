const CHANNEL_TABS = [
  { value: "all", label: "All" },
  { value: "email", label: "Email" },
  { value: "whatsapp", label: "WhatsApp" },
];

export default function FilterBar({ projectId, onProjectIdChange, projects, channel, onChannelChange }) {
  const knownProjects = projects || [];
  const hasCurrentProject = knownProjects.some((p) => p.project_id === projectId);

  return (
    <div className="filter-bar">
      <div className="filter-bar__row">
        <span className="filter-bar__icon-badge">🔍</span>
        <div className="filter-bar__divider" />
        <div className="filter-bar__field">
          <label className="filter-bar__label">
            Project Name<span className="required">*</span>
          </label>
          <select
            className="filter-bar__input"
            value={projectId}
            onChange={(e) => onProjectIdChange(e.target.value)}
          >
            {!hasCurrentProject && <option value={projectId}>{projectId}</option>}
            {knownProjects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.project_name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-bar__tabs">
          {CHANNEL_TABS.map((tab) => (
            <button
              key={tab.value}
              className={`channel-tab ${channel === tab.value ? "channel-tab--active" : ""}`}
              onClick={() => onChannelChange(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
