# MarTech Content Agent

Multi-agent system that generates marketing content (email, WhatsApp/SMS) for a real-estate MarTech/CRM platform, and saves it to a content library with a creative ID that the campaign-setup UI's "Choose Content" step can look up.

Stack: FastAPI + LangGraph orchestrator, Gemini (generation + embeddings), Pinecone (brochure retrieval), SQLite (content library).

## Status

Built incrementally, per the build order below. Steps 3+ need real `GEMINI_API_KEY` / `PINECONE_API_KEY` values.

- [x] 1. Repo scaffold + shared Pydantic contracts (`app/models/`)
- [x] 2. Email + WhatsApp content agents, built and tested against a fake LLM client (`app/agents/email_agent.py`, `app/agents/whatsapp_agent.py`)
- [x] 3. Context agent + brochure indexing CLI (Pinecone) (`app/agents/context_agent.py`, `app/ingest/brochure_ingest.py`)
- [x] 4. Asset agent (`app/agents/asset_agent.py`)
- [x] 5. Orchestrator (LangGraph) wiring everything together (`app/agents/orchestrator.py`)
- [x] 6. Compliance/QA agent (`app/agents/compliance_agent.py`)
- [x] 7. Content library agent + SQLite store + FastAPI endpoint (`app/agents/library_agent.py`, `app/storage/content_library_store.py`, `app/api/main.py`)
- [x] 8. Content-library browse UI (Sirrus.ai design language) (`frontend/`)
- [x] 9. "New Content" form wired to `/campaigns/run` from the frontend (`frontend/src/components/CampaignForm.jsx`)
- [x] 10. `CampaignBrief`/`EmailBrief`/`WhatsAppBrief` split — see below
- [x] 11. Visual channel previews: WhatsApp phone mockup, Email preview with a Preview/HTML Code tab switcher
- [x] 12. Generate → review → NLP-revise → explicit save workflow — see below
- [x] 13. Channel-picker overlay on "+ New Content" (single channel per generation), "Save as Draft" alongside "Save to Library", WhatsApp icon in brand green, "Approved" pill hidden (only non-approved statuses show a pill)
- [x] 14. Single-screen workspace (inputs + live-generated preview side by side, no separate review screen), WhatsApp `message_variants` (2+ A/B options with emoji), taller WhatsApp phone mockup, image shown in the WhatsApp preview when selected, Campaign ID dropped from the form (generated client-side)
- [x] 15. Rich multi-block email HTML (hero, highlight panels, pricing callout, secondary image, CTA, footer), "View in browser" action on the email preview
- [x] 16. `DELETE /content-library/{creative_id}` + delete action on both the library card and the detail panel; project pickers (browse + create) default to Crown Greens
- [x] 17. `template_name` field (form input at creation, shown on cards/detail panel instead of "Primary"/variant_label), "Use this content" CTA removed everywhere (View + Delete only), browse list refreshes immediately after saving new content
- [x] 18. Editable `template_name` (pencil icon, inline edit, `PATCH /content-library/{creative_id}`) with ellipsis truncation for long names; unique `template_id` (`E####`/`WA####`, generated at save time) shown on cards/detail panel instead of the raw `creative_id`
- [x] 19. Subject-line chip picker (tick-to-select, stable order, `+ Generate more options` via a dedicated endpoint that doesn't touch the rest of the draft), emojis in subject lines, and a loading-spinner state in the preview panel while content is generating
- [x] 20. WhatsApp messages formatted like a real business alert (line-broken opening/details/closing, `*bold*` on key facts) instead of one paragraph, rendered in `WhatsAppPreview` with actual bold text
- [x] 21. Google-search-style suggestion dropdown on Key Message (pre-populated example briefs, filtered/highlighted as you type); WhatsApp CTA Text replaced with 5-6 preset CTA chips + custom "Other" (select up to 2), the two CTAs A/B tested one per message variant via `WhatsAppDraft.cta_variants`
- [x] 22. Fixed Key Message field losing its full width when wrapped for suggestions; "Download HTML ⬇" action on the email preview, alongside "View in browser"
- [x] 23. Content tag (`Service` / `Promotional Communication`) required at save time, stored via a `content_tag` SQLite migration on `content_library`, shown on browse cards and the detail panel (`ContentTag` enum in `app/models/library.py`)
- [x] 24. Optional manual image picker on the email form: an asset-bank grid (up to 4, first pick = hero) that overrides the AI's tag-based auto-select via `EmailBrief.selected_asset_ids`, fetched in caller-given order by `AssetAgent.get_by_ids` and enforced in the prompt (hero + smaller gallery row) when set; leaving it empty keeps the original AI-picks-best-match behavior
- [x] 25. Image editor: a freeform canvas editor (`frontend/src/components/ImageEditor.jsx`) that adds draggable, styled text layers onto any existing asset-bank image, with an AI "suggest text" action (`ImageOverlayTextAgent`, `POST /assets/suggest-overlay-text`), then flattens and saves the result as a brand-new asset-bank entry (`POST /assets/generated`, `LocalAssetStore.save_generated_asset`) that immediately shows up in the image picker
- [x] 26. Image picker and image editor extended to WhatsApp content creation: single-image picker (`ImagePicker` gained a `maxImages` prop -- 1 swaps the selection on click instead of filling slots) wired to `WhatsAppBrief.selected_asset_id`, and the same "Create image template" entry point/modal now opens from either channel's panel
- [x] 27. Image editor advanced pass: generalized "layers" into typed elements (`text` / `shape` / `button`) with a shared `elementBox`/`drawScene`/hit-test so all three drag, layer-order (front/back), and export the same way; a CTA-button element (solid/outline/pill presets); a background/backer panel element (color, opacity, corner radius) that inserts behind existing content; a freeform crop tool (draggable corner handles + square/9:16/original presets) that remaps element positions into the cropped frame; the font list expanded via Google Fonts, loaded through `document.fonts.load()` before every draw so canvas text never silently falls back to the system font; and curated font-pairing presets that drop in a ready-made heading + body text pair in one click (`+ Add heading & body text`) rather than requiring a target element to be selected first
- [x] 28. New homepage (`frontend/src/components/HomePage.jsx`), now the default landing view: hero with Create/Browse actions, a real content-composition Insights dashboard per project (`InsightsAgent`, `GET /insights`) covering subject-line length/words/emoji, top words, image usage, CTA phrasing, and service-vs-promotional mix for both channels — plus a clearly-labeled illustrative benchmark section, since this app has no send/open/click tracking to report real performance from. An interactive architecture explainer (`ArchitectureModal.jsx`, opened via the "?" button) diagrams the actual LangGraph pipeline with click-to-expand descriptions per agent.
- [x] 29. New "Usage" tab (`frontend/src/components/UsagePage.jsx`): tracks every real Gemini call this app makes (`UsageStore`, `GET /usage`, `PUT /usage/cap`) via a decorator that wraps the existing `LLMClient`/`EmbeddingClient` protocols (`UsageTrackingLLMClient`/`UsageTrackingEmbeddingClient` in `app/agents/usage_tracking_client.py`) so no content agent had to change. Shows requests made today, a user-supplied daily cap compared against actual usage, a live rate-limit warning, and a by-purpose breakdown -- since Gemini's API exposes no endpoint for your real account quota, this is deliberately self-tracked "requests made through this app," never presented as a live pull from Google.
- [x] 30. "✉ Send Email" on the email preview (`EmailPreview.jsx`, both in the create workspace and the saved-content detail panel): sends the actual rendered HTML to a one-off recipient via `POST /send-email`, authenticated as a real Gmail address over SMTP (`GmailSmtpSender` in `app/agents/email_sender.py`, App Password auth so it lands in that account's own Sent folder) -- gated behind a native `confirm()` since it's a real, irreversible send, and returns a clear 503 rather than a raw SMTP error until `GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD` are set in `.env`.
- [x] 31. Per-template send history: every send now records `{creative_id, to_email, sent_at}` (`EmailSendStore` in `app/storage/email_send_store.py`, sharing the content-library SQLite file since a record only makes sense attached to a creative_id) via `POST /send-email`'s new optional `creative_id` field, retrievable via `GET /content-library/{creative_id}/sends`. `EmailPreview.jsx` shows it as a "Sent to" list right under the send form (with a live count on the button itself), fetched whenever a `creativeId` prop is present -- an unsaved draft preview has no creative_id yet, so it sends without logging anything, matching "sending unsaved content" already being allowed.
- [x] 32. Detail panel polish: widened `.detail-panel` (680px -> 920px) since the email toolbar (Preview/HTML Code tabs, View in browser, Download HTML, Send Email) was crowding at the old width; removed the panel's own Delete button/footer (deleting a template still works from its card in Browse Library -- this was a duplicate, more accident-prone entry point right next to Send); and the saved-entry view now uses the same `SubjectLinePicker` chip UI as the create workflow (with `onGenerateMore` made optional so it can be reused without a "+ Generate more" affordance) so a user can pick which saved subject-line variant to actually send, instead of always sending the one that happened to be primary at save time.
- [x] 33. Editable subject line before send (`EmailPreview.jsx`): a pencil icon next to "Subject:" in the preview chrome swaps it for an inline input, seeded from whichever subject-line chip is selected. This is a local-only override, same pattern as the HTML Code tab -- it drives the preview text, the downloaded filename slug, and the `POST /send-email` payload, but is never written back to the content library, and picking a different subject chip discards the edit and resyncs.
- [x] 34. Fly.io deployment (`Dockerfile`, `fly.toml`, `docker-entrypoint.sh`): one container builds the React frontend and serves it plus the API from the same origin (`app/api/main.py` mounts the built `frontend_dist` after every API route, so production needs no CORS at all -- `frontend/src/api.js`'s `VITE_API_BASE` now defaults via `??` instead of `||` so an explicitly empty build-time value, meaning "same origin," isn't discarded in favor of the local dev URL). A persistent Fly volume at `/app/data` keeps the SQLite stores and asset bank across restarts/redeploys; the entrypoint script seeds it with the demo project facts/assets from the image the first time the volume is empty, and never touches it again after that.
- [x] 35. Dimension badges on `ImagePicker` thumbnails (`asset.width`×`asset.height`, top-right corner) -- `Asset` already carried these fields for every asset, they just weren't surfaced in the picker UI, so there was no way to tell a 1200x628 email banner shot from a 1080x1920 WhatsApp story shot before selecting it. Also folded into each thumbnail's hover tooltip alongside its tags.
- [ ] 36. Intake agent (step-by-step wizard UX with "Decide for me" / "Ask follow-up questions" / "Send answer") — not started

## Why it's structured this way

- **`app/models/`** — one Pydantic model per agent's input/output contract. These are written first and shared by every agent, so "what does the Context agent hand to the Email agent" is answered by reading one file (`context.py`), not by reverse-engineering prompt strings.
- **`app/agents/llm_client.py`** / **`embedding_client.py`** — agents depend on small protocols (`generate_json`, `embed`), not on the Gemini SDK directly. `GeminiClient`/`GeminiEmbeddingClient` are the real implementations; tests use fakes that return canned data. This is what let the content agents get built and tested in step 2 before Pinecone/retrieval existed — swapping the LLM provider later is also a one-class change, not a rewrite.
- **`app/storage/`** — one thin class per external system (Pinecone, SQLite, local asset folder, project facts JSON). Same reasoning: swap Pinecone for Chroma, or SQLite for Postgres, without touching any agent.
- **Structured facts vs. retrieval are deliberately separate.** RERA number, pricing, possession date live in `data/projects/{id}/facts.json` and are read directly, not retrieved via similarity search — those are the numbers a content agent must reproduce exactly, so they come from a source of truth, not a nearest-neighbor lookup. Retrieval (Pinecone) only supplies supporting brochure prose.
- **Compliance is enforced twice** for the one thing that can't be trusted to prompting alone: `WhatsAppContentAgent` tells the model not to pick an image when `whatsapp_needs_image=False`, *and* forces `image_asset_id = None` in code afterward, because an LLM ignoring an instruction is a normal failure mode, not an edge case.
- **Compliance checks against `ProjectFacts`, not just the draft.** "Flag misleading claims" only means something if there's a ground truth to compare against, so `ComplianceAgent.review()` takes the same facts the content agents were given. Only the missing-RERA-disclaimer case is auto-fixed in code; everything else (guaranteed-language, price/date mismatches, invalid HTML, char limits, bad personalization tokens) blocks and surfaces as an issue for a human to look at.
- **The Orchestrator (`app/agents/orchestrator.py`) is a LangGraph `StateGraph`**: Context + Asset agents fan out from `START` and run in parallel, join, then fan back into whichever channel(s) the brief actually asked for. Each channel's `content → compliance → library` chain runs independently — a rejected draft shows up as a status note with its issue codes, not a creative ID, so callers can tell "channel was skipped" apart from "channel failed compliance."
- **Real bug caught along the way**: the HTML compliance check initially flagged Gemini's self-closed `<br/>` tags as broken markup, because Python's `HTMLParser.handle_startendtag` calls both `handle_starttag` *and* `handle_endtag` by default. Fixed by overriding `handle_startendtag` to no-op (see `compliance_agent.py`); there's a regression test for it.
- **A second real bug, caught the same way**: the price-verification regex matched "1.28 Cr" but silently failed on "87 Lakhs" (plural) — meaning a hallucinated Lakh-denominated price would never have been flagged. Fixed in `compliance_agent.py`.
- **`ContentTag` is deliberately independent of `Purpose`.** `CampaignBrief.purpose` (`product_announcement`, `promo_sale`, ...) is a generation input — it shapes what the copy says. `content_tag` (`service` / `promotional_communication`) is a library-organization label chosen at save time, for whoever (e.g. a compliance/ops reviewer) needs to filter "is this a transactional service message or a marketing push" without caring which specific purpose drove the copy. Kept as a plain `str` field on `ContentLibraryEntry` (not the enum type) to match the existing `template_name`/`template_id` columns, which stay string-typed for storage flexibility with old rows that predate the column.
- **Manual image selection overrides the AI, it doesn't just hint it.** `EmailBrief.selected_asset_ids` (empty by default = old auto-pick behavior unchanged) is resolved via `AssetAgent.get_by_ids`, which returns assets in the *caller's* order rather than store order — the first id is the intended hero. When set, `email_agent.py`'s prompt-builder swaps out the normal "pick assets whose tags best match" guidance entirely for a directive naming the first asset HERO and the rest a smaller gallery row, so the model can't silently second-guess the user's picks or drop one.
- **The image editor treats a saved template as just another asset, not a new concept.** There's no separate "templates" table or endpoint — `save_generated_asset` writes the flattened PNG next to the rest of the project's asset files and appends one more record to the same `metadata.json` the asset bank already reads. That's what lets a freshly-created template show up in the image picker immediately, with zero new plumbing between "create" and "use in a campaign."
- **Real bug caught during verification: the exported PNG had the editor's own UI baked into it.** `ImageEditor`'s canvas drew a dashed selection-outline around whichever text layer was active, and the original `handleSave` exported that same live canvas via `toDataURL()` — so any template saved while a layer was selected permanently had a purple dashed box burned into the image. Fixed by extracting the draw routine (`drawScene`) so export always renders to a fresh offscreen canvas with `selectedLayerId` omitted, instead of screenshotting the visible one.
- **A second real bug, found the same way: locally-generated images displayed everywhere except inside the email preview.** The preview iframe uses `sandbox=""` so AI-generated HTML can never execute script -- but with no `allow-same-origin`, the iframe gets an opaque origin, which Chrome's Private Network Access checks classify as a "public" address space. Subresource requests from an opaque origin to a private/loopback target (our own `127.0.0.1` asset server) get silently blocked with no console error, just a broken `<img>` -- while external `ibb.co` images, not being a private-network target, were unaffected. Fixed by adding `allow-same-origin` (without `allow-scripts`) to the sandbox attribute, which keeps the iframe's origin as `http://localhost:5174` -- same address-space classification as the app itself -- without granting the generated HTML any script-execution capability.
- **WhatsApp's image override is a single force-set, email's is a prompt directive.** `WhatsAppDraft.image_asset_id` is one field, so `whatsapp_agent.py` can just overwrite it in code after the LLM call whenever `WhatsAppBrief.selected_asset_id` is set -- no ambiguity about which asset goes where, unlike email's hero-plus-gallery layout which has to stay a prompt instruction because "where each image goes" isn't reducible to overwriting one field.
- **`elementBox`/`drawScene`/hit-test are one function each, shared across all three element types**, rather than a text path, a button path, and a shape path each reimplementing "where is this thing and what's its footprint." A type-specific branch inside each shared function is the only per-type code; drag, layer-order, and export all move for free when a new element type is added, since they operate on `elementBox`'s output, not on the element directly.
- **A background/backer panel is inserted at the front of the elements array, not the back.** Elements render in array order, so "insert at index 0" is the entire "always behind existing and future text" behavior -- no explicit z-index field, no sort step, just array position doing double duty as paint order.
- **Crop remaps element positions by converting through absolute canvas px, not by scaling percentages directly.** `xPct`/`yPct` are fractions of the *current* canvas, so cropping (which changes what the canvas frames) has to first turn a fraction back into an absolute position, subtract the crop rect's offset, and re-express *that* as a fraction of the new, smaller canvas -- skip the offset subtraction and every element would drift toward the corner being cropped away instead of staying anchored to the same point in the photo.
- **Canvas text needs an explicit `document.fonts.load()` before every draw, not just a `<link>` tag.** Linking a Google Fonts stylesheet doesn't make the browser fetch a given weight/style until something on the page actually renders text in it -- and `fillText` on a `<canvas>` doesn't count as "using" a font the way a DOM element does, so the very first draw in a newly-picked font would silently fall back to the system font with no error. Fixed by awaiting `document.fonts.load(exact-same-spec-as-ctx.font)` for every element before each draw (both the live canvas and the export canvas), keyed off the literal font shorthand string so it can't drift from what's actually drawn.
- **Bug caught during verification: the crop tool's resize handles were nearly unhittable.** The corner hit-test used a 16px (canvas-space) radius rendered as a tiny 10px square -- on a display-scaled canvas that's a handful of CSS pixels, easy to miss even with precise coordinates. Widened the hit radius to 28px and the visual handle to an 18px circle with a white outline, confirmed by testing the exact same drag that silently failed before now succeeding.
- **The homepage Insights are composition analytics, deliberately never framed as performance.** This app generates content but never sends it or tracks opens/clicks/replies, so there is no real engagement data anywhere in the system -- `InsightsAgent` only ever computes things that are actually true of the saved library (subject-line length, word frequency, emoji/image usage, CTA phrasing, service-vs-promotional mix). The one section that shows sample open/reply-rate numbers (`IllustrativeBenchmarks.jsx`) uses static, hand-picked values that are never computed from real content, and is visually and textually marked as illustrative everywhere it appears (amber dashed panel, a "SAMPLE DATA" badge, and an explanatory line) so it can't be mistaken for a real result.
- **The architecture diagram's node layout and edges mirror `orchestrator.py`'s actual `StateGraph` shape**, not a simplified marketing version of it -- brief in, fan out to Context + Asset agents in parallel, join into the channel content agent, then compliance, then library save. Each node's description was written from the real agent code (e.g. Asset Agent's "explicit pick always overrides the tag search" is the same override behavior `_email_candidate_assets`/`_whatsapp_candidate_assets` implement), so the explainer stays accurate as documentation, not just as a picture.
- **Usage tracking is a decorator around the existing `LLMClient`/`EmbeddingClient` protocols, not a change to any agent.** `UsageTrackingLLMClient`/`UsageTrackingEmbeddingClient` wrap the real Gemini clients and are swapped in only at the `main.py` wiring layer (`get_orchestrator`, `get_image_text_agent`) -- `EmailContentAgent`, `WhatsAppContentAgent`, `ContextAgent`, and `ImageOverlayTextAgent` never know usage is being recorded, so tracking can be added to (or removed from) any future Gemini call site the same way, with zero agent-code changes.
- **The daily cap is a number you supply, never one this app claims to know.** Gemini's API has no endpoint that exposes an account's real quota or remaining requests -- `UsageStore` only ever counts calls made through this app itself and compares that against whatever cap you type into the Usage tab. `rate_limited_today` is the one piece of *real* signal from Google: `UsageTrackingLLMClient` pattern-matches failed calls for 429/quota/rate-limit language and flags it, since an actual rejection from Gemini is ground truth in a way a self-reported cap number can never be.
- **Email sending uses an App Password over SMTP, not OAuth.** Gmail API + OAuth2 is the more "proper" integration, but it needs a Google Cloud project, a configured consent screen, and a one-time browser-based consent flow -- real setup cost for what this app only ever needs once: sending as one person's own address. An App Password (Google Account -> Security -> App Passwords) gets the same result -- authenticated SMTP as a real Gmail address, landing in that account's own Sent folder -- with a single revocable code pasted into `.env`, no Cloud project required. `EmailSender` is a `Protocol`, though, so swapping in OAuth later (e.g. to send as *other* people's addresses, which App Passwords can't do) is a new class behind the same interface, not a rewrite.
- **`get_email_sender()` returns `None`, not a sender that fails, when unconfigured.** The alternative -- constructing a `GmailSmtpSender` with empty credentials -- would only fail at actual send time with a confusing raw `smtplib` error. Returning `None` lets the endpoint give a specific, actionable 503 ("add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env") before ever touching the network, and lets tests default every fixture to the same "not configured" state a fresh clone of this repo would actually be in.
- **A send is only logged when it actually succeeded.** `send_store.record(...)` runs *after* `sender.send(...)` returns without raising, not before -- a failed SMTP send (bad address, auth error, network blip) must never show up in a template's "Sent to" history, since that history is meant to answer "did this actually go out," not "did someone click the button."

### Brief schema (`app/models/brief.py`)

The Orchestrator's entry point is `CampaignRequest { project_id, campaign_id, campaign_brief, email_brief?, whatsapp_brief? }`.
`campaign_brief` (`purpose`, `key_message`, `cta_text`, `audience_tone`) is shared across every channel; `email_brief`
and `whatsapp_brief` hold only what's unique to that channel. Which channels run is implied by which channel briefs
are present — there's no separate `channels` list, so "email_brief is set but email shouldn't run" isn't a state
that can exist. `WhatsAppBrief.cta_required` decides whether `campaign_brief.cta_text` actually reaches the
WhatsApp draft (`WhatsAppDraft.cta` is `Optional` for exactly this reason); `EmailBrief.imagery` decides whether
the Email agent ever sees real candidate assets at all.

A step-by-step **Intake agent** (wizard UX: "Decide for me" auto-fills a field, "Ask follow-up questions" shows
guidance, "Send answer" submits and advances) is planned but not yet built — the current frontend form asks every
field in one shot.

### Generate / review / revise / save workflow

Nothing lands in the content library just because content was generated. `POST /campaigns/run` (the original
one-shot endpoint) still generates *and* saves in a single call, but the frontend no longer uses it. Instead:

1. `POST /campaigns/generate` — runs Context + Asset + the requested content agent(s) + Compliance, returns
   `{email?: {draft, approved, issues}, whatsapp?: {...}}`. Nothing is persisted.
2. `POST /campaigns/revise/email` / `POST /campaigns/revise/whatsapp` — takes the current draft plus a plain-language
   `instruction` ("make it shorter", "add more urgency"), re-runs that one content agent with the current draft and
   the instruction folded into the prompt, re-checks Compliance, and returns the updated draft. Can be called
   repeatedly. Still nothing is persisted.
3. `POST /content-library/email` / `POST /content-library/whatsapp` — the only endpoints that write to the library.
   Takes whatever draft the caller currently has (original or revised) and saves it.

`EmailContentAgent.revise()` / `WhatsAppContentAgent.revise()` reuse the same prompt-building logic as `generate()`,
just with `CURRENT DRAFT` + `USER'S REQUESTED CHANGE` prepended — the model still can't hallucinate facts, prices,
or a different CTA than the brief specifies, only apply the requested edit within those constraints.

On the frontend, `GenerateWorkspace` owns the whole flow on one screen: the brief form on the left, and the live
`EmailPreview`/`WhatsAppPreview` (from step 11) on the right with a "Refine this content" box (revise) and
"Save as Draft" / "Save to Library" buttons (save) once a draft exists. A blocking compliance issue disables
"Save to Library" until a revision resolves it. `campaign_id` is generated client-side (`camp-<timestamp>-<random>`)
instead of asked for — it only exists to group saved content, so there was nothing for the user to meaningfully type.

### WhatsApp multi-variant drafts

`WhatsAppDraft.message_variants` is a list (2+), the same shape as `EmailDraft.subject_lines` — the agent is
prompted to return distinct A/B-style options (different opening lines/emphasis, not just reword), with `cta` and
`image_asset_id` shared across all variants since only the message copy itself should vary. `WhatsAppPreview`
renders an "Option 1 / Option 2" tab switcher above the phone mockup; compliance's char-limit check runs per
variant and names which one is over the limit, rather than failing the whole draft on one offender.

**Real bug caught while verifying the image-in-preview requirement**: `AssetAgent.search()` scored candidate assets
by tag-overlap against the campaign's `key_message`, and returned an empty list when nothing scored above zero.
An empty candidate list didn't stop the WhatsApp agent from being told "you must select an image" — it just
hallucinated a plausible-looking `asset_id` (e.g. `promo_sale_image_placeholder`) that doesn't exist in the asset
bank, so the preview silently showed no image. Fixed by falling back to the project's other assets when nothing
matches by tag, so the model always chooses from real candidates (`app/agents/asset_agent.py`).

### Multi-block email design

`EmailContentAgent`'s prompt (`app/agents/email_agent.py`) used to ask for a plain paragraph email with one
optional header image, which read as flat text-in-a-box rather than a real marketing email. `LAYOUT_GUIDANCE` now
spells out a concrete section structure (hero image → intro → 2-3 highlight/amenity panels on tinted backgrounds
→ pricing callout → optional secondary image → CTA button → footer disclaimer) and requires table-based,
inline-styled, email-client-safe HTML (no CSS grid/flexbox, no `<style>` blocks, no scripts) within a 600px
canvas. `_IMAGERY_GUIDANCE` was extended so `use_asset_bank` can pick a distinct hero *and* secondary asset
instead of just one header image, and `placeholder_blocks` now places a styled placeholder wherever the hero/
secondary blocks would go. This is deliberately still just prompt/guidance text, not a template engine — the model
composes the actual copy and color choices per project, `LAYOUT_GUIDANCE` only constrains the shape.

`EmailPreview.jsx` has a "View in browser ↗" button next to the Preview/HTML Code tabs: it resolves `asset://`
placeholders the same way the iframe preview does, wraps the result in the same email-canvas HTML, and opens it as
a `Blob` URL in a new tab (falling back to navigating the current tab if the browser blocks the popup) — useful
because the in-app iframe preview is deliberately small and `sandbox=""`, so a full-size view is the only way to
see exactly what the email looks like at real size.

### Template names + deleting content

`ContentLibraryEntry.template_name` is a user-facing label (e.g. "Diwali Launch Offer"), separate from
`variant_label` (an internal A/B slot name like `"primary"`/`"subject_a"`) and `creative_id` (the system ID).
Cards and the detail panel show `template_name` as the headline instead of `variant_label`/"Primary", which read
as an internal implementation detail with no meaning to the user. It's a required field in `GenerateWorkspace`,
collected once up front and threaded through to the save call.

Existing rows in `data/content_library.db` predate this column, so `ContentLibraryStore` runs a one-time
`ALTER TABLE ... ADD COLUMN template_name ... DEFAULT 'Untitled Template'` migration on startup (guarded by a
`PRAGMA table_info` check) rather than requiring the DB file to be recreated — real saved content shouldn't
disappear just because a field was added.

`DELETE /content-library/{creative_id}` (`ContentLibraryStore.delete()` / `ContentLibraryAgent.delete()`) backs a
delete action on both the card (trash icon) and the detail panel ("Delete" button) — window.confirm()'d, since
this can't be undone. The old "Use this content" CTA was removed everywhere (App.jsx's `handleUse`, both
components) since nothing downstream actually consumed a "selected" creative_id — View + Delete is all a card
needs.

**Real bug caught while verifying**: after saving new content and clicking "Done", the browse list didn't refresh
if you were still looking at the same project — `App.jsx`'s content-fetching `useEffect` only reruns when its
dependencies (`projectId`, `channel`) actually change, and `onDone` was calling `setProjectId` with a value that
was usually already current. Fixed by adding a `refreshToken` counter, bumped on `onDone` and included in the
effect's dependency array, so a save always triggers a refetch regardless of whether the project changed.

### Template IDs + inline rename

`ContentLibraryEntry.template_id` is a short, human-scannable code -- `E####`/`E#####` for email, `WA####`/
`WA#####` for whatsapp -- generated once at save time (`ContentLibraryStore.generate_template_id`, retried
against `template_id_exists` until unique) and shown on cards/the detail panel in place of the long, mostly
opaque `creative_id`. `creative_id` still exists and is still the DB primary key / URL parameter for every
`/content-library/*` endpoint -- `template_id` is purely a friendlier display label, not a new identity scheme.

`EditableTemplateName.jsx` is the shared pencil-icon-click-to-edit control used by both `ContentCard` and
`DetailPanel`: click the pencil, edit inline, Enter/blur saves via `PATCH /content-library/{creative_id}`
(`ContentLibraryStore.rename_template_name`), Escape cancels. Long names are CSS-truncated with an ellipsis
(`max-width` + `text-overflow: ellipsis`) rather than trimmed server-side, so the full name is always still
there on hover (`title` attribute) and in the stored record.

Existing rows predate `template_id`, so the same `_ensure_column`-style migration used for `template_name` adds
the column and then backfills every existing row with a freshly generated, guaranteed-unique id (tracked via an
in-memory `used` set during the one-time backfill, rather than re-querying per row).

**Data anomaly found, not caused by this change**: while verifying this feature, most of the project's real saved
`crown-greens` content (13 of 16 entries) was found missing from `data/content_library.db` compared to a backup
taken earlier the same session -- discovered via `PRAGMA integrity_check` (clean) and diffing row counts, not
via any delete request in the server logs. The cause wasn't identified (no bulk-delete code path exists anywhere
in this codebase, and no test touches the real DB file). Backups from both before and after the loss are kept at
`data/content_library.db.bak-*`; the user asked to leave the live DB as-is rather than restore, so it wasn't
touched.

### Subject line picker + generation loader

`SubjectLinePicker.jsx` renders `EmailDraft.subject_lines` as selectable pill chips (a tick marks the selected
one) instead of the old plain "Subject: {subjectLines[0]}" text. Chip order is deliberately kept stable while the
user is choosing -- selecting a chip only moves a tick, it doesn't reshuffle positions, which the reference UI the
user attached also does. The reordering that makes the selected line "primary" (`subject_lines[0]`, the
convention every other reader -- `EmailPreview`'s chrome, `contentPreview.js`'s card title, compliance -- already
assumes) happens exactly once, in `GenerateWorkspace.handleSave`, right before the save call.

"+ Generate more options" hits a new `POST /campaigns/generate-more-subject-lines` endpoint
(`EmailContentAgent.generate_more_subject_lines`) rather than reusing `/campaigns/revise/email` --  revise
regenerates the whole draft (and would silently replace the existing subject line options), where this only
needs 3 more headlines appended to the list, leaving `html_body` and the user's current selection untouched. The
email agent's system prompts (`generate`, `revise`, and the new `generate_more_subject_lines`) all got the same
emoji guidance already used for WhatsApp: a tasteful emoji in most subject lines, skipped entirely for
`b2b_professional`/`internal_team` audiences.

`GenerateWorkspace`'s preview column shows a dedicated `workspace__loading` state (spinner + "Generating your
{channel} content…") whenever `submitting` is true, replacing whatever was in that column before -- previously,
regenerating left the *old* draft on screen with no visual indication a new one was on the way, which read as the
click not having registered.

### WhatsApp message formatting

The WhatsApp agent's prompts (`generate`, `revise`) got a `FORMATTING_GUIDANCE` block modeled on real
business-alert WhatsApp messages (bank/insurer notification style, per user-supplied reference screenshots):
a one-line opening hook, then -- when there are 2+ discrete facts -- a "Label: value" line per fact rather than
weaving them into a sentence, then a short closing line, with blank lines (`\n\n`) between each part and 2-4 key
facts per variant wrapped in WhatsApp's own bold markdown (single asterisks, `*like this*`). This is prompt
guidance only, not a template -- the model still writes the actual copy per campaign.

`WhatsAppPreview.jsx` already had `white-space: pre-wrap` on the bubble text (so `\n` was rendering correctly
without any change), but was printing `*bold*` markdown as literal asterisks -- `formatWhatsAppText()` now splits
on that pattern and renders matched spans as real `<strong>` text, matching how the message actually looks in
WhatsApp itself.

### Key message suggestions + WhatsApp dual-CTA picker

`KeyMessageField.jsx` wraps the Key Message textarea with a Google-search-style dropdown: a static list of
example campaign briefs, shown on focus and filtered by substring match as the user types, with the matched
portion bolded. Suggestion clicks use `onMouseDown` + `preventDefault` (not `onClick`) so the pick registers
before the textarea's `onBlur` closes the dropdown — the standard fix for this exact race in a blur-to-close
pattern.

`CtaPicker.jsx` replaces WhatsApp's plain CTA Text input with 6 preset CTA chips (tick-to-select, up to 2) plus
an "Other" chip that reveals a custom-text input counted as one of the 2 slots. This is WhatsApp-only -- Email
keeps the original single CTA Text input, since one button label is all an email needs.

Picking 2 CTAs isn't just a convenience for typing -- `WhatsAppDraft.cta` became `cta_variants: Optional[list[str]]`
(parallel to `message_variants`, same idea as `EmailDraft.subject_lines`), so the two selected CTAs are A/B
tested one per message variant instead of every variant sharing a single button. `WhatsAppBrief.secondary_cta_text`
carries the 2nd pick (`CampaignBrief.cta_text`, already shared with Email, carries the 1st/primary one); the
agent's `_normalize_cta_variants` rebuilds `cta_variants` by cycling through whichever 1-2 CTA options were given
whenever the model returns the wrong length or skips the field, so a misbehaving LLM response can't leave a
variant without a CTA. `ComplianceAgent._check_char_limit` and `_extract_text` were updated to check/read CTA
length per-variant instead of one shared value. `WhatsAppPreview.jsx` shows `cta_variants[selectedTab]` under the
bubble, with the same `cta_variants?.length ? ... : draft.cta ? [draft.cta] : []` backward-compat fallback
pattern used elsewhere in this app for older saved records.

**Real bug caught while verifying**: `.campaign-form__field` relies on flexbox stretch (`display:flex;
flex-direction:column`, default `align-items:stretch`) to make its child fill the full width -- that only works
when the child is a *direct* flex item. Wrapping the Key Message textarea in `KeyMessageField`'s own
`<div className="key-message-field">` (needed so the suggestions dropdown has a positioning anchor) made the
*div* the flex item instead, and the textarea inside it fell back to browser-default intrinsic sizing --
narrower than the form, and tall from an unrelated stray resize-drag. Fixed by giving `.campaign-form__textarea`
an explicit `width: 100%; box-sizing: border-box;` so it fills its container regardless of whether it's a direct
flex child or nested inside a wrapper div.

`EmailPreview.jsx` also gained a "Download HTML ⬇" button next to "View in browser" -- same resolved HTML (asset
placeholders swapped for real URLs), delivered as an actual file save via a temporary `<a download>` element
rather than a new tab, with the filename slugified from the active subject line.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # includes requirements.txt + pytest
cp .env.example .env                  # fill in GEMINI_API_KEY / PINECONE_API_KEY when ready
```

## Run tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

## Index a project's brochures (one-time, per project)

```bash
python -m app.ingest.brochure_ingest --project-id proj-skyline --pdf-dir data/projects/proj-skyline/brochures
```

Also add `data/projects/{project_id}/facts.json` (structured facts) and `data/assets/{project_id}/metadata.json`
(asset sidecar) — see the `proj-skyline` sample data for the shape of both.

## Run the API

```bash
source venv/bin/activate
uvicorn app.api.main:app --port 8123
```

- `POST /campaigns/run` — one-shot generate + save (used by tests/scripts; the frontend uses the split flow below)
- `POST /campaigns/generate` — generate drafts for the requested channels, does not save
- `POST /campaigns/revise/email`, `POST /campaigns/revise/whatsapp` — revise a draft from a plain-language instruction, does not save
- `POST /content-library/email`, `POST /content-library/whatsapp` — save a draft to the library, returns `{creative_id}`
- `GET /content-library/{creative_id}` — fetch one entry (what the campaign-setup "Choose Content" step calls)
- `GET /content-library?project_id=...&channel=...` — list/filter entries
- `GET /assets?project_id=...` — resolve `asset_id` -> real URL (content-library entries only store IDs)

## Run the browse UI

```bash
cd frontend
npm install
npm run dev   # http://localhost:5174, expects the API on :8123
```

Styled to match the Sirrus.ai journey-builder/campaign-setup screenshots: lavender-gray background, indigo
headings, white cards with pastel accent borders per channel, gradient CTA buttons, rounded status pills. Each
card's "Use this content" button is the integration point for the real "Choose Content" step — it currently just
confirms the selection locally rather than writing back into a live campaign-setup form.

## Deploying (Fly.io)

The app is stateful (SQLite files + generated/uploaded images live on local disk under `data/`), so it needs a
real persistent disk, not a serverless/stateless host. `Dockerfile` builds one container that serves both the
API and the built React frontend from the same origin (`app/api/main.py` mounts `frontend_dist` after every API
route, so no CORS is needed in production); `fly.toml` attaches a persistent volume at `/app/data` so the
content library, usage tracking, email send history, and asset bank all survive restarts and redeploys.
`docker-entrypoint.sh` seeds that volume with the demo project facts/assets (`data/projects`, `data/assets`)
the first time it's empty, then never touches it again.

```bash
# one-time
curl -L https://fly.io/install.sh | sh
fly auth login

# from the repo root
fly apps create martech-content-agent   # pick a different name if taken; update fly.toml's `app =` line to match
fly volumes create data --size 1 --region sin   # match fly.toml's primary_region

fly secrets set \
  GEMINI_API_KEY=... \
  PINECONE_API_KEY=... \
  GMAIL_ADDRESS=... \
  GMAIL_APP_PASSWORD=... \
  API_PUBLIC_BASE_URL=https://martech-content-agent.fly.dev   # your actual app URL

fly deploy
```

`fly deploy` builds remotely (no local Docker install needed). `API_PUBLIC_BASE_URL` matters because
`LocalAssetStore` uses it to build the absolute `<img src>` URLs the frontend loads asset-bank images from —
left at its `http://127.0.0.1:8123` default, images would be broken in production even though the API itself
works fine. Re-run `fly deploy` for any future code change; the volume (and everything on it) is untouched by
that.

## Note on Python version

This machine only has Python 3.9.6 available (no 3.10+, no pyenv/brew found). Pydantic models here use `typing.Optional`/`typing.Union` instead of the `X | None` operator syntax for that reason — functionally identical, just 3.9-compatible. If a newer Python becomes available later this isn't worth changing.
