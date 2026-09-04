import { useEffect, useState } from "react";
import Header from "./components/Header";
import FilterBar from "./components/FilterBar";
import ContentCard from "./components/ContentCard";
import DetailPanel from "./components/DetailPanel";
import GenerateWorkspace from "./components/GenerateWorkspace";
import ChannelPickerModal from "./components/ChannelPickerModal";
import HomePage from "./components/HomePage";
import UsagePage from "./components/UsagePage";
import { deleteContent, listAssets, listContent, listProjects } from "./api";
import "./App.css";

function humanize(id) {
  return id
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function App() {
  const [view, setView] = useState("home");
  const [projectId, setProjectId] = useState("crown-greens");
  const [projects, setProjects] = useState([]);
  const [channel, setChannel] = useState("all");
  const [entries, setEntries] = useState([]);
  const [assetsById, setAssetsById] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [toast, setToast] = useState(null);
  const [showChannelPicker, setShowChannelPicker] = useState(false);
  const [newContentChannel, setNewContentChannel] = useState(null);
  // Bumped whenever the browse list needs a refetch that isn't already
  // implied by projectId/channel changing -- e.g. returning from "New
  // Content" for the project already being browsed.
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!projectId.trim()) {
      setEntries([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    listContent({ projectId: projectId.trim(), channel })
      .then((data) => {
        if (!cancelled) setEntries(data);
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
  }, [projectId, channel, refreshToken]);

  useEffect(() => {
    if (!projectId.trim()) {
      setAssetsById({});
      return;
    }
    let cancelled = false;
    listAssets(projectId.trim())
      .then((assets) => {
        if (cancelled) return;
        setAssetsById(Object.fromEntries(assets.map((a) => [a.asset_id, a])));
      })
      .catch(() => {
        if (!cancelled) setAssetsById({});
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function handleDelete(entry) {
    try {
      await deleteContent(entry.creative_id);
      setEntries((prev) => prev.filter((e) => e.creative_id !== entry.creative_id));
      setSelected((prev) => (prev?.creative_id === entry.creative_id ? null : prev));
      setToast(`Deleted ${entry.template_name}.`);
    } catch (err) {
      setToast(`Failed to delete: ${err.message}`);
    }
    setTimeout(() => setToast(null), 3000);
  }

  function handleRename(updatedEntry) {
    setEntries((prev) => prev.map((e) => (e.creative_id === updatedEntry.creative_id ? updatedEntry : e)));
    setSelected((prev) => (prev?.creative_id === updatedEntry.creative_id ? updatedEntry : prev));
  }

  return (
    <div className="page">
      <Header />

      <main className="page__content">
        <div className="view-tabs">
          <div className="view-tabs__links">
            <button
              className={`view-tab-link ${view === "home" ? "view-tab-link--active" : ""}`}
              onClick={() => setView("home")}
            >
              Home
            </button>
            <button
              className={`view-tab-link ${view === "browse" ? "view-tab-link--active" : ""}`}
              onClick={() => setView("browse")}
            >
              Browse Library
            </button>
            <button
              className={`view-tab-link ${view === "usage" ? "view-tab-link--active" : ""}`}
              onClick={() => setView("usage")}
            >
              Usage
            </button>
          </div>
          <button
            className="new-content-btn"
            onClick={() => (view === "create" ? setView("browse") : setShowChannelPicker(true))}
          >
            {view === "create" ? "← Back to Library" : "+ New Content"}
          </button>
        </div>

        {showChannelPicker && (
          <ChannelPickerModal
            onCancel={() => setShowChannelPicker(false)}
            onContinue={(pickedChannel) => {
              setNewContentChannel(pickedChannel);
              setShowChannelPicker(false);
              setView("create");
            }}
          />
        )}

        {view === "home" && (
          <HomePage
            projects={projects}
            projectId={projectId}
            onProjectIdChange={setProjectId}
            onGoBrowse={() => setView("browse")}
            onGoCreate={() => setShowChannelPicker(true)}
          />
        )}

        {view === "usage" && <UsagePage />}

        {view === "create" && newContentChannel && (
          <GenerateWorkspace
            channel={newContentChannel}
            onChangeChannel={() => setShowChannelPicker(true)}
            onDone={(generatedProjectId) => {
              setProjectId(generatedProjectId);
              setChannel("all");
              setRefreshToken((t) => t + 1);
              setView("browse");
            }}
          />
        )}

        {view === "browse" && (
          <>
            <FilterBar
              projectId={projectId}
              onProjectIdChange={setProjectId}
              projects={projects}
              channel={channel}
              onChannelChange={setChannel}
            />

            {loading && <div className="state-message">Loading content&hellip;</div>}
            {error && <div className="state-message state-message--error">{error}</div>}
            {!loading && !error && entries.length === 0 && (
              <div className="state-message">
                No content found{projectId.trim() ? ` for "${projectId.trim()}"` : ""}. Use "New Campaign" to
                generate some.
              </div>
            )}

            {!loading && !error && entries.length > 0 && (
              <div className="content-grid">
                {entries.map((entry) => (
                  <ContentCard
                    key={entry.creative_id}
                    entry={entry}
                    onSelect={setSelected}
                    onDelete={handleDelete}
                    onRename={handleRename}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      <DetailPanel
        entry={selected}
        onClose={() => setSelected(null)}
        onRename={handleRename}
        assetsById={assetsById}
        businessName={humanize(projectId)}
      />

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
