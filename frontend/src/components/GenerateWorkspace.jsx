import { useEffect, useState } from "react";
import EmailPreview from "./EmailPreview";
import WhatsAppPreview from "./WhatsAppPreview";
import SubjectLinePicker from "./SubjectLinePicker";
import CtaPicker from "./CtaPicker";
import KeyMessageField from "./KeyMessageField";
import ImagePicker from "./ImagePicker";
import ImageEditor from "./ImageEditor";
import {
  generateCampaign,
  generateMoreSubjectLines,
  listAssets,
  listProjects,
  reviseEmail,
  reviseWhatsapp,
  saveEmail,
  saveWhatsapp,
} from "../api";

const PURPOSE_OPTIONS = [
  { value: "product_announcement", label: "Product Announcement" },
  { value: "newsletter", label: "Newsletter" },
  { value: "promo_sale", label: "Promo / Sale" },
  { value: "event_invite", label: "Event Invite" },
  { value: "welcome_onboarding", label: "Welcome / Onboarding" },
  { value: "transactional_receipt", label: "Transactional Receipt" },
  { value: "follow_up_nudge", label: "Follow-up Nudge" },
  { value: "payment_possession_reminder", label: "Payment / Possession Reminder" },
  { value: "other", label: "Other" },
];

const AUDIENCE_TONE_OPTIONS = [
  { value: "consumers_casual", label: "Consumers - Casual" },
  { value: "consumers_premium", label: "Consumers - Premium" },
  { value: "b2b_professional", label: "B2B - Professional" },
  { value: "internal_team", label: "Internal Team" },
  { value: "community_newsletter", label: "Community Newsletter" },
];

const EMAIL_LENGTH_OPTIONS = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
];

const EMAIL_IMAGERY_OPTIONS = [
  { value: "text_only", label: "Text only" },
  { value: "placeholder_blocks", label: "Placeholder image blocks" },
  { value: "use_asset_bank", label: "Use asset bank" },
];

const WHATSAPP_LENGTH_OPTIONS = [
  { value: "short", label: "Short (under 150 chars)" },
  { value: "standard", label: "Standard (under 300 chars)" },
];

const CONTENT_TAG_OPTIONS = [
  { value: "service", label: "Service" },
  { value: "promotional_communication", label: "Promotional Communication" },
];

const CHANNEL_LABELS = { email: "Email", whatsapp: "WhatsApp" };

function humanize(id) {
  return id
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// campaign_id is only used internally to group saved content -- the user
// never needs to see or type it, so generate one instead of asking for it.
function generateCampaignId() {
  return `camp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

// Chip order stays stable while the user is picking -- reordering only
// happens once, right before save, so index 0 (the "primary" subject line
// everywhere else in the app) reflects whichever chip they selected.
function withSelectedFirst(lines, selectedIndex) {
  const copy = [...lines];
  const [chosen] = copy.splice(selectedIndex, 1);
  return [chosen, ...copy];
}

export default function GenerateWorkspace({ channel, onChangeChannel, onDone }) {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("crown-greens");

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((list) => {
        if (cancelled) return;
        setProjects(list);
        // Keep the crown-greens default if it's actually in the list;
        // otherwise fall back to whatever project does exist.
        if (list.length && !list.some((p) => p.project_id === projectId)) {
          setProjectId(list[0].project_id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [templateName, setTemplateName] = useState("");
  const [contentTag, setContentTag] = useState("promotional_communication");
  const [purpose, setPurpose] = useState("promo_sale");
  const [purposeOtherDescription, setPurposeOtherDescription] = useState("");
  const [keyMessage, setKeyMessage] = useState("");
  const [ctaText, setCtaText] = useState("");
  const [whatsappCtas, setWhatsappCtas] = useState([]);
  const [audienceTone, setAudienceTone] = useState("consumers_premium");

  const [designSystemId, setDesignSystemId] = useState("");
  const [emailLength, setEmailLength] = useState("medium");
  const [emailImagery, setEmailImagery] = useState("use_asset_bank");
  const [selectedAssetIds, setSelectedAssetIds] = useState([]);

  const [whatsappCtaRequired, setWhatsappCtaRequired] = useState(true);
  const [whatsappImageRequired, setWhatsappImageRequired] = useState(true);
  const [whatsappLength, setWhatsappLength] = useState("standard");
  const [whatsappSelectedAssetId, setWhatsappSelectedAssetId] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const [requestContext, setRequestContext] = useState(null);
  const [draftState, setDraftState] = useState(null);
  const [assetsById, setAssetsById] = useState({});
  const [selectedSubjectIndex, setSelectedSubjectIndex] = useState(0);
  const [generatingMoreSubjects, setGeneratingMoreSubjects] = useState(false);
  const [showImageEditor, setShowImageEditor] = useState(false);

  // Same shape as the campaign_brief sent to /campaigns/generate -- reused
  // here so the image editor's "Suggest text with AI" has the same context
  // (purpose/key message/tone) the content agents get, without waiting for
  // an actual generation to happen first.
  function currentCampaignBrief() {
    return {
      purpose,
      purpose_other_description: purpose === "other" ? purposeOtherDescription.trim() || "Custom" : null,
      key_message: keyMessage.trim() || "Promote this project",
      cta_text: (channel === "whatsapp" ? whatsappCtas[0] : ctaText.trim()) || "Learn more",
      audience_tone: audienceTone,
    };
  }

  function handleImageTemplateCreated(asset) {
    setAssetsById((prev) => ({ ...prev, [asset.asset_id]: asset }));
    if (channel === "whatsapp") {
      setWhatsappSelectedAssetId(asset.asset_id);
    } else {
      setSelectedAssetIds((prev) => (prev.length < 4 ? [...prev, asset.asset_id] : prev));
    }
    setShowImageEditor(false);
  }

  useEffect(() => {
    // Fetched by projectId (not requestContext) so the image picker has
    // thumbnails to show before the user has generated anything yet.
    if (!projectId.trim()) return;
    let cancelled = false;
    listAssets(projectId.trim())
      .then((assets) => {
        if (!cancelled) setAssetsById(Object.fromEntries(assets.map((a) => [a.asset_id, a])));
      })
      .catch(() => {
        if (!cancelled) setAssetsById({});
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    // Selections are project-specific -- clear them if the user switches
    // projects so a stale asset_id from another project's bank can't leak in.
    setSelectedAssetIds([]);
    setWhatsappSelectedAssetId("");
  }, [projectId]);

  async function handleGenerate(e) {
    e.preventDefault();
    setFormError(null);

    const primaryCta = channel === "whatsapp" ? whatsappCtas[0] || "" : ctaText.trim();
    if (!projectId.trim() || !templateName.trim() || !keyMessage.trim() || !primaryCta) {
      setFormError(
        channel === "whatsapp"
          ? "Template Name, Project, Key Message, and at least one CTA are required."
          : "Template Name, Project, Key Message, and CTA Text are required."
      );
      return;
    }
    if (purpose === "other" && !purposeOtherDescription.trim()) {
      setFormError("Please describe the purpose when 'Other' is selected.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        campaign_id: generateCampaignId(),
        project_id: projectId.trim(),
        campaign_brief: {
          purpose,
          purpose_other_description: purpose === "other" ? purposeOtherDescription.trim() : null,
          key_message: keyMessage.trim(),
          cta_text: primaryCta,
          audience_tone: audienceTone,
        },
        email_brief:
          channel === "email"
            ? {
                design_system_id: designSystemId.trim() || null,
                length: emailLength,
                imagery: emailImagery,
                selected_asset_ids: selectedAssetIds,
              }
            : undefined,
        whatsapp_brief:
          channel === "whatsapp"
            ? {
                cta_required: whatsappCtaRequired,
                image_required: whatsappImageRequired,
                length: whatsappLength,
                secondary_cta_text: whatsappCtas[1] || null,
                selected_asset_id: whatsappSelectedAssetId || null,
              }
            : undefined,
      };
      const drafts = await generateCampaign(payload);
      const result = drafts[channel];
      setRequestContext(payload);
      setSelectedSubjectIndex(0);
      setDraftState({
        draft: result.draft,
        approved: result.approved,
        issues: result.issues,
        instruction: "",
        revising: false,
        savingAs: null,
        error: null,
        creativeId: null,
        savedStatus: null,
      });
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function updateDraftState(patch) {
    setDraftState((prev) => ({ ...prev, ...patch }));
  }

  async function handleRevise() {
    if (!draftState.instruction.trim()) return;
    updateDraftState({ revising: true, error: null });
    try {
      const revise = channel === "email" ? reviseEmail : reviseWhatsapp;
      const briefKey = channel === "email" ? "email_brief" : "whatsapp_brief";
      const payload = {
        project_id: requestContext.project_id,
        campaign_brief: requestContext.campaign_brief,
        [briefKey]: requestContext[briefKey],
        current_draft: draftState.draft,
        instruction: draftState.instruction.trim(),
      };
      const result = await revise(payload);
      setSelectedSubjectIndex(0);
      updateDraftState({
        draft: result.draft,
        approved: result.approved,
        issues: result.issues,
        instruction: "",
        revising: false,
      });
    } catch (err) {
      updateDraftState({ revising: false, error: err.message });
    }
  }

  async function handleGenerateMoreSubjectLines() {
    setGeneratingMoreSubjects(true);
    try {
      const result = await generateMoreSubjectLines({
        project_id: requestContext.project_id,
        campaign_brief: requestContext.campaign_brief,
        existing_subject_lines: draftState.draft.subject_lines,
      });
      updateDraftState({
        draft: { ...draftState.draft, subject_lines: [...draftState.draft.subject_lines, ...result.subject_lines] },
      });
    } catch (err) {
      updateDraftState({ error: err.message });
    } finally {
      setGeneratingMoreSubjects(false);
    }
  }

  async function handleSave(asDraft) {
    updateDraftState({ savingAs: asDraft ? "draft" : "approved", error: null });
    try {
      const save = channel === "email" ? saveEmail : saveWhatsapp;
      const draftToSave =
        channel === "email"
          ? { ...draftState.draft, subject_lines: withSelectedFirst(draftState.draft.subject_lines, selectedSubjectIndex) }
          : draftState.draft;
      const result = await save({
        project_id: requestContext.project_id,
        campaign_id: requestContext.campaign_id,
        draft: draftToSave,
        template_name: templateName.trim(),
        content_tag: contentTag,
        as_draft: asDraft,
      });
      updateDraftState({
        savingAs: null,
        creativeId: result.creative_id,
        savedStatus: asDraft ? "draft" : "approved",
      });
    } catch (err) {
      updateDraftState({ savingAs: null, error: err.message });
    }
  }

  const blockingIssues = draftState?.issues.filter((i) => i.severity === "blocking") || [];
  const warningIssues = draftState?.issues.filter((i) => i.severity === "warning") || [];

  return (
    <div className="workspace">
      <div className="workspace__col workspace__col--form">
        <div className="campaign-form__channel-banner">
          Creating <strong>{CHANNEL_LABELS[channel]}</strong> content
          <button type="button" className="campaign-form__change-channel" onClick={onChangeChannel}>
            Change channel
          </button>
        </div>

        <form className="campaign-form" onSubmit={handleGenerate}>
          <div className="campaign-form__field">
            <label className="filter-bar__label">
              Project Name<span className="required">*</span>
            </label>
            <select className="filter-bar__input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              {projects.length === 0 && <option value={projectId}>{humanize(projectId)}</option>}
              {projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.project_name}
                </option>
              ))}
            </select>
          </div>

          <div className="campaign-form__field">
            <label className="filter-bar__label">
              Template Name<span className="required">*</span>
            </label>
            <input
              className="filter-bar__input"
              placeholder="Eg: Diwali Launch Offer"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
          </div>

          <div className="campaign-form__field">
            <label className="filter-bar__label">
              Content Tag<span className="required">*</span>
            </label>
            <select className="filter-bar__input" value={contentTag} onChange={(e) => setContentTag(e.target.value)}>
              {CONTENT_TAG_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <h4 className="campaign-form__section-title">Campaign brief</h4>

          <div className="campaign-form__row">
            <div className="campaign-form__field">
              <label className="filter-bar__label">
                Purpose<span className="required">*</span>
              </label>
              <select className="filter-bar__input" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                {PURPOSE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="campaign-form__field">
              <label className="filter-bar__label">
                Audience / Tone<span className="required">*</span>
              </label>
              <select
                className="filter-bar__input"
                value={audienceTone}
                onChange={(e) => setAudienceTone(e.target.value)}
              >
                {AUDIENCE_TONE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {purpose === "other" && (
            <div className="campaign-form__field">
              <label className="filter-bar__label">
                Describe the purpose<span className="required">*</span>
              </label>
              <input
                className="filter-bar__input"
                placeholder="Eg: post-visit survey follow-up"
                value={purposeOtherDescription}
                onChange={(e) => setPurposeOtherDescription(e.target.value)}
              />
            </div>
          )}

          <div className="campaign-form__field">
            <label className="filter-bar__label">
              Key Message<span className="required">*</span>
            </label>
            <KeyMessageField value={keyMessage} onChange={setKeyMessage} />
          </div>

          <div className="campaign-form__field">
            <label className="filter-bar__label">
              CTA Text<span className="required">*</span>
            </label>
            {channel === "whatsapp" ? (
              <CtaPicker onChange={setWhatsappCtas} />
            ) : (
              <input
                className="filter-bar__input"
                placeholder="Eg: Book a site visit"
                value={ctaText}
                onChange={(e) => setCtaText(e.target.value)}
              />
            )}
          </div>

          <h4 className="campaign-form__section-title">{CHANNEL_LABELS[channel]} settings</h4>

          {channel === "email" ? (
            <div className="campaign-form__channel-panel">
              <div className="campaign-form__row">
                <div className="campaign-form__field">
                  <label className="filter-bar__label">Length</label>
                  <select
                    className="filter-bar__input"
                    value={emailLength}
                    onChange={(e) => setEmailLength(e.target.value)}
                  >
                    {EMAIL_LENGTH_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="campaign-form__field">
                  <label className="filter-bar__label">Imagery</label>
                  <select
                    className="filter-bar__input"
                    value={emailImagery}
                    onChange={(e) => setEmailImagery(e.target.value)}
                  >
                    {EMAIL_IMAGERY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {emailImagery === "use_asset_bank" && (
                <div className="campaign-form__field">
                  <div className="image-picker__header">
                    <label className="filter-bar__label">Choose images (optional)</label>
                    <button type="button" className="btn btn--ghost image-picker__create-btn" onClick={() => setShowImageEditor(true)}>
                      🖉 Create image template
                    </button>
                  </div>
                  <ImagePicker
                    assets={Object.values(assetsById)}
                    selectedIds={selectedAssetIds}
                    onChange={setSelectedAssetIds}
                  />
                </div>
              )}

              <div className="campaign-form__field">
                <label className="filter-bar__label">Design System ID (optional)</label>
                <input
                  className="filter-bar__input"
                  placeholder="Eg: brand-template-2026"
                  value={designSystemId}
                  onChange={(e) => setDesignSystemId(e.target.value)}
                />
              </div>
            </div>
          ) : (
            <div className="campaign-form__channel-panel">
              <div className="campaign-form__row">
                <label className="campaign-form__checkbox">
                  <input
                    type="checkbox"
                    checked={whatsappCtaRequired}
                    onChange={(e) => setWhatsappCtaRequired(e.target.checked)}
                  />
                  Include a CTA
                </label>
                <label className="campaign-form__checkbox">
                  <input
                    type="checkbox"
                    checked={whatsappImageRequired}
                    onChange={(e) => setWhatsappImageRequired(e.target.checked)}
                  />
                  Include an image
                </label>
              </div>
              <div className="campaign-form__field">
                <label className="filter-bar__label">Length</label>
                <select
                  className="filter-bar__input"
                  value={whatsappLength}
                  onChange={(e) => setWhatsappLength(e.target.value)}
                >
                  {WHATSAPP_LENGTH_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {whatsappImageRequired && (
                <div className="campaign-form__field">
                  <div className="image-picker__header">
                    <label className="filter-bar__label">Choose image (optional)</label>
                    <button type="button" className="btn btn--ghost image-picker__create-btn" onClick={() => setShowImageEditor(true)}>
                      🖉 Create image template
                    </button>
                  </div>
                  <ImagePicker
                    assets={Object.values(assetsById)}
                    selectedIds={whatsappSelectedAssetId ? [whatsappSelectedAssetId] : []}
                    onChange={(ids) => setWhatsappSelectedAssetId(ids[0] || "")}
                    maxImages={1}
                  />
                </div>
              )}
            </div>
          )}

          {showImageEditor && (
            <ImageEditor
              projectId={projectId.trim()}
              assets={Object.values(assetsById)}
              campaignBrief={currentCampaignBrief()}
              onClose={() => setShowImageEditor(false)}
              onCreated={handleImageTemplateCreated}
            />
          )}

          {formError && <div className="state-message state-message--error">{formError}</div>}

          <button className="btn btn--cta campaign-form__submit" type="submit" disabled={submitting}>
            {submitting ? "Generating…" : draftState ? "Regenerate Content" : "Generate Content"}
          </button>
        </form>
      </div>

      <div className="workspace__col workspace__col--preview">
        {submitting && (
          <div className="workspace__loading">
            <span className="workspace__spinner" />
            Generating your {CHANNEL_LABELS[channel]} content&hellip;
          </div>
        )}

        {!submitting && !draftState && (
          <div className="workspace__empty">
            Fill in the form and click <strong>Generate Content</strong> to see the {CHANNEL_LABELS[channel]}{" "}
            preview here.
          </div>
        )}

        {!submitting && draftState && (
          <div className="review-drafts__panel">
            {blockingIssues.length > 0 && (
              <div className="state-message state-message--error">
                Not approved yet — {blockingIssues.map((i) => i.message).join("; ")}
              </div>
            )}
            {warningIssues.length > 0 && (
              <div className="review-drafts__warning">{warningIssues.map((i) => i.message).join("; ")}</div>
            )}

            {channel === "email" ? (
              <>
                <SubjectLinePicker
                  subjectLines={draftState.draft.subject_lines}
                  selectedIndex={selectedSubjectIndex}
                  onSelect={setSelectedSubjectIndex}
                  onGenerateMore={handleGenerateMoreSubjectLines}
                  generating={generatingMoreSubjects}
                />
                <EmailPreview
                  subjectLines={draftState.draft.subject_lines}
                  selectedSubjectIndex={selectedSubjectIndex}
                  htmlBody={draftState.draft.html_body}
                  assetsById={assetsById}
                  creativeId={draftState.creativeId}
                />
              </>
            ) : (
              <WhatsAppPreview
                draft={draftState.draft}
                imageUrl={draftState.draft.image_asset_id ? assetsById?.[draftState.draft.image_asset_id]?.url : null}
                businessName={humanize(requestContext.project_id)}
              />
            )}

            <div className="review-drafts__refine">
              <label className="filter-bar__label">Refine this content</label>
              <textarea
                className="filter-bar__input campaign-form__textarea"
                placeholder="Eg: make it shorter, add more urgency, mention the pool first"
                value={draftState.instruction}
                onChange={(e) => updateDraftState({ instruction: e.target.value })}
              />
              <div className="review-drafts__actions">
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={handleRevise}
                  disabled={draftState.revising || !draftState.instruction.trim()}
                >
                  {draftState.revising ? "Revising…" : "Revise"}
                </button>
                {draftState.creativeId ? (
                  <span className="review-drafts__saved">
                    Saved{draftState.savedStatus === "draft" ? " as draft" : ""}: {draftState.creativeId}
                  </span>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => handleSave(true)}
                      disabled={draftState.savingAs !== null}
                    >
                      {draftState.savingAs === "draft" ? "Saving…" : "Save as Draft"}
                    </button>
                    <button
                      type="button"
                      className="btn btn--cta"
                      onClick={() => handleSave(false)}
                      disabled={draftState.savingAs !== null || blockingIssues.length > 0}
                      title={
                        blockingIssues.length > 0
                          ? "Resolve the blocking issue(s) above, or save as a draft instead"
                          : undefined
                      }
                    >
                      {draftState.savingAs === "approved" ? "Saving…" : "Save to Library"}
                    </button>
                  </>
                )}
              </div>
              {draftState.error && <div className="state-message state-message--error">{draftState.error}</div>}
            </div>

            {draftState.creativeId && (
              <button type="button" className="new-content-btn" onClick={() => onDone(requestContext.project_id)}>
                Done
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
