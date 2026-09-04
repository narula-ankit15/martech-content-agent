// "??" (not "||") so an explicitly empty VITE_API_BASE -- meaning "call the
// API on this same origin," used in production where one server serves both
// the built frontend and the API -- doesn't fall back to the dev default.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8123";

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function listContent({ projectId, channel }) {
  const params = new URLSearchParams({ project_id: projectId });
  if (channel && channel !== "all") params.set("channel", channel);
  return request(`/content-library?${params.toString()}`);
}

export function getContent(creativeId) {
  return request(`/content-library/${encodeURIComponent(creativeId)}`);
}

export function deleteContent(creativeId) {
  return request(`/content-library/${encodeURIComponent(creativeId)}`, { method: "DELETE" });
}

export function renameContent(creativeId, templateName) {
  return request(`/content-library/${encodeURIComponent(creativeId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_name: templateName }),
  });
}

export function runCampaign(brief) {
  return request("/campaigns/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
  });
}

export function listAssets(projectId) {
  return request(`/assets?${new URLSearchParams({ project_id: projectId }).toString()}`);
}

export function listProjects() {
  return request("/projects");
}

export function getInsights(projectId) {
  return request(`/insights?${new URLSearchParams({ project_id: projectId }).toString()}`);
}

export function getUsage() {
  return request("/usage");
}

export function setUsageCap(dailyCap) {
  return request("/usage/cap", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ daily_cap: dailyCap }),
  });
}

function postJson(path, payload) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateCampaign(payload) {
  return postJson("/campaigns/generate", payload);
}

export function reviseEmail(payload) {
  return postJson("/campaigns/revise/email", payload);
}

export function reviseWhatsapp(payload) {
  return postJson("/campaigns/revise/whatsapp", payload);
}

export function generateMoreSubjectLines(payload) {
  return postJson("/campaigns/generate-more-subject-lines", payload);
}

export function saveEmail(payload) {
  return postJson("/content-library/email", payload);
}

export function saveWhatsapp(payload) {
  return postJson("/content-library/whatsapp", payload);
}

export function saveGeneratedAsset(payload) {
  return postJson("/assets/generated", payload);
}

export function suggestOverlayText(payload) {
  return postJson("/assets/suggest-overlay-text", payload);
}

export function sendEmail(payload) {
  return postJson("/send-email", payload);
}

export function getEmailSends(creativeId) {
  return request(`/content-library/${encodeURIComponent(creativeId)}/sends`);
}
