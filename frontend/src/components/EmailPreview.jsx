import { useEffect, useState } from "react";
import { getEmailSends, sendEmail } from "../api";

const ASSET_SCHEME_RE = /asset:\/\/([a-zA-Z0-9_-]+)/g;

function resolveAssetPlaceholders(htmlBody, assetsById) {
  // The email agent doesn't know real asset URLs, so it's instructed to emit
  // src="asset://{asset_id}" instead of inventing one -- resolve those here.
  return htmlBody.replace(ASSET_SCHEME_RE, (match, assetId) => assetsById?.[assetId]?.url || match);
}

function buildPreviewDoc(htmlBody, assetsById) {
  // Wraps a raw fragment in email-safe defaults (max-width, font, background)
  // so it renders like it would in an actual inbox, not a bare fragment.
  const resolved = resolveAssetPlaceholders(htmlBody, assetsById);
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body { margin: 0; padding: 24px; background: #f1f0f7; font-family: Arial, Helvetica, sans-serif; }
  .email-canvas { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  img { max-width: 100%; height: auto; }
</style>
</head>
<body>
  <div class="email-canvas">${resolved}</div>
</body>
</html>`;
}

export default function EmailPreview({ subjectLines, selectedSubjectIndex = 0, htmlBody, assetsById, creativeId }) {
  const [tab, setTab] = useState("preview");
  const [code, setCode] = useState(htmlBody);
  const [showSendPanel, setShowSendPanel] = useState(false);
  const [sendTo, setSendTo] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [sendHistory, setSendHistory] = useState([]);
  const activeSubject = subjectLines[selectedSubjectIndex] ?? subjectLines[0];
  const [subjectText, setSubjectText] = useState(activeSubject);
  const [editingSubject, setEditingSubject] = useState(false);

  useEffect(() => {
    setCode(htmlBody);
  }, [htmlBody]);

  useEffect(() => {
    // A different subject-line chip was picked (or a different entry was
    // opened) -- drop any in-progress manual edit and resync.
    setSubjectText(activeSubject);
    setEditingSubject(false);
  }, [activeSubject]);

  useEffect(() => {
    // Only a saved library entry has a creative_id -- an unsaved draft
    // preview has nothing to look up a history for yet.
    if (!creativeId) {
      setSendHistory([]);
      return;
    }
    let cancelled = false;
    getEmailSends(creativeId)
      .then((records) => {
        if (!cancelled) setSendHistory(records);
      })
      .catch(() => {
        if (!cancelled) setSendHistory([]);
      });
    return () => {
      cancelled = true;
    };
  }, [creativeId]);

  function handleViewInBrowser() {
    // Blob URL (not a data: URI) so the tab is a real same-origin-ish
    // document -- large HTML survives, and it isn't subject to the
    // preview iframe's sandbox="" restrictions.
    const blob = new Blob([buildPreviewDoc(code, assetsById)], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    // Open blank first (without the "noopener" feature string, which makes
    // some browsers always return null even on success) so we can reliably
    // tell whether it was actually blocked, then strip window.opener by
    // hand -- same security effect as noopener, without losing detection.
    const newTab = window.open("", "_blank");
    if (newTab) {
      newTab.opener = null;
      newTab.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } else {
      // Genuinely blocked -- fall back to navigating this tab.
      window.location.href = url;
    }
  }

  function handleDownloadHtml() {
    const blob = new Blob([buildPreviewDoc(code, assetsById)], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const slug =
      (subjectText || "email")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 60) || "email";
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  async function handleSend(e) {
    e.preventDefault();
    const to = sendTo.trim();
    if (!to || sending) return;
    // A real, irreversible send from the user's own configured Gmail
    // account -- one more explicit confirmation beyond just clicking
    // "Send", since there's no undo once Gmail has accepted it.
    const confirmed = window.confirm(`Send this email to ${to}? This sends a real email from your configured Gmail account.`);
    if (!confirmed) return;
    setSending(true);
    setSendResult(null);
    try {
      await sendEmail({
        to,
        subject: subjectText,
        html_body: buildPreviewDoc(code, assetsById),
        creative_id: creativeId || null,
      });
      setSendResult({ ok: true, message: `Sent to ${to}.` });
      if (creativeId) {
        setSendHistory((prev) => [{ to_email: to, sent_at: new Date().toISOString() }, ...prev]);
      }
      setSendTo("");
    } catch (err) {
      setSendResult({ ok: false, message: err.message || "Couldn't send the email." });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="email-preview">
      <div className="email-preview__chrome">
        <span className="email-preview__dot email-preview__dot--red" />
        <span className="email-preview__dot email-preview__dot--amber" />
        <span className="email-preview__dot email-preview__dot--green" />
        {editingSubject ? (
          <input
            type="text"
            className="email-preview__subject-input"
            value={subjectText}
            autoFocus
            onChange={(e) => setSubjectText(e.target.value)}
            onBlur={() => setEditingSubject(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                setEditingSubject(false);
              } else if (e.key === "Escape") {
                setSubjectText(activeSubject);
                setEditingSubject(false);
              }
            }}
          />
        ) : (
          <>
            <span className="email-preview__subject">Subject: {subjectText}</span>
            <button
              type="button"
              className="email-preview__subject-edit"
              onClick={() => setEditingSubject(true)}
              aria-label="Edit subject line"
              title="Edit subject line"
            >
              ✎
            </button>
          </>
        )}
      </div>

      <div className="email-preview__tabs">
        <button
          className={`email-preview__tab ${tab === "preview" ? "email-preview__tab--active" : ""}`}
          onClick={() => setTab("preview")}
          type="button"
        >
          Preview
        </button>
        <button
          className={`email-preview__tab ${tab === "code" ? "email-preview__tab--active" : ""}`}
          onClick={() => setTab("code")}
          type="button"
        >
          HTML Code
        </button>
        <button className="email-preview__view-in-browser" onClick={handleViewInBrowser} type="button">
          View in browser ↗
        </button>
        <button className="email-preview__download" onClick={handleDownloadHtml} type="button">
          Download HTML ⬇
        </button>
        <button
          className="email-preview__download"
          onClick={() => {
            setShowSendPanel((v) => !v);
            setSendResult(null);
          }}
          type="button"
        >
          ✉ Send Email{creativeId && sendHistory.length > 0 ? ` (${sendHistory.length})` : ""}
        </button>
      </div>

      {showSendPanel && (
        <div className="email-preview__send-panel-wrap">
          <form className="email-preview__send-panel" onSubmit={handleSend}>
            <input
              type="email"
              required
              className="filter-bar__input"
              placeholder="recipient@example.com"
              value={sendTo}
              onChange={(e) => setSendTo(e.target.value)}
            />
            <button className="btn btn--cta" type="submit" disabled={sending}>
              {sending ? "Sending…" : "Send"}
            </button>
          </form>
          {creativeId && (
            <div className="email-preview__send-history">
              {sendHistory.length === 0 ? (
                <p className="insights-empty">Not sent yet.</p>
              ) : (
                <>
                  <p className="email-preview__send-history-label">Sent to:</p>
                  <ul className="email-preview__send-history-list">
                    {sendHistory.map((record, i) => (
                      <li key={i}>
                        <span>{record.to_email}</span>
                        <span className="email-preview__send-history-date">
                          {new Date(record.sent_at).toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>
      )}
      {sendResult && (
        <div className={`state-message ${sendResult.ok ? "" : "state-message--error"}`}>{sendResult.message}</div>
      )}

      {tab === "preview" ? (
        <iframe
          className="email-preview__iframe"
          title="email-preview"
          // No "allow-scripts", so generated HTML still can't execute code.
          // "allow-same-origin" alone is needed so this stays same-origin
          // (http://localhost:5174) instead of an opaque origin -- an opaque
          // origin gets classified by Chrome's Private Network Access checks
          // as a "public" address space, which blocks subresource requests to
          // locally-hosted image-template assets on 127.0.0.1 without ever
          // surfacing a visible network error, only a broken <img>.
          sandbox="allow-same-origin"
          srcDoc={buildPreviewDoc(code, assetsById)}
        />
      ) : (
        <textarea
          className="email-preview__code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
        />
      )}
      {tab === "code" && (
        <p className="email-preview__code-hint">
          Editing here updates the Preview tab live — it isn't saved back to the content library.
        </p>
      )}
    </div>
  );
}
