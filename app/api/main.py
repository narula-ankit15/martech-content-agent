import base64
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents.asset_agent import AssetAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.context_agent import ContextAgent
from app.agents.email_agent import EmailContentAgent
from app.agents.email_sender import EmailSender, GmailSmtpSender
from app.agents.embedding_client import GeminiEmbeddingClient
from app.agents.image_text_agent import ImageOverlayTextAgent
from app.agents.insights_agent import InsightsAgent
from app.agents.library_agent import ContentLibraryAgent
from app.agents.llm_client import GeminiClient
from app.agents.orchestrator import Orchestrator
from app.agents.usage_tracking_client import UsageTrackingEmbeddingClient, UsageTrackingLLMClient
from app.agents.whatsapp_agent import WhatsAppContentAgent
from app.config import get_settings
from app.models import (
    Asset,
    CampaignBrief,
    CampaignRequest,
    Channel,
    ComplianceIssue,
    ContentLibraryEntry,
    ContentStatus,
    ContentTag,
    EmailBrief,
    EmailDraft,
    EmailSendRecord,
    ProjectInsights,
    ProjectSummary,
    UsageSummary,
    WhatsAppBrief,
    WhatsAppDraft,
)
from app.storage.asset_store import LocalAssetStore
from app.storage.content_library_store import ContentLibraryStore
from app.storage.email_send_store import EmailSendStore
from app.storage.project_facts_store import ProjectFactsStore
from app.storage.usage_store import UsageStore
from app.storage.vector_store import PineconeVectorStore

app = FastAPI(title="MarTech Content Agent API")

# Local dev only: the browse UI (Vite on 5174) calls this API directly from
# the browser. Tighten this to a real origin allowlist before deploying anywhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Image-template PNGs rendered by the frontend's image editor get saved to
# disk (see LocalAssetStore.save_generated_asset) and need a real URL the
# browser can load -- this mount is what turns a file on disk into
# GET /asset-files/{project_id}/generated/{asset_id}.png.
app.mount("/asset-files", StaticFiles(directory=get_settings().asset_bank_path), name="asset-files")


# Dependencies are built lazily behind @lru_cache (not at import time) so
# the API can start and serve /content-library reads even before
# GEMINI/PINECONE keys are configured, and so tests can override just the
# pieces that need faking via app.dependency_overrides.


@lru_cache
def get_library_store() -> ContentLibraryStore:
    return ContentLibraryStore(get_settings().content_library_db_path)


@lru_cache
def get_asset_store() -> LocalAssetStore:
    s = get_settings()
    return LocalAssetStore(s.asset_bank_path, public_url_base=s.api_public_base_url)


@lru_cache
def get_usage_store() -> UsageStore:
    return UsageStore(get_settings().usage_db_path)


@lru_cache
def get_email_sender() -> Optional[EmailSender]:
    # None (not a broken sender) when unconfigured, so the endpoint can
    # return a clear "not set up yet" error instead of a raw SMTP failure.
    s = get_settings()
    if not s.gmail_address or not s.gmail_app_password:
        return None
    return GmailSmtpSender(s.gmail_address, s.gmail_app_password)


@lru_cache
def get_email_send_store() -> EmailSendStore:
    return EmailSendStore(get_settings().content_library_db_path)


@lru_cache
def get_image_text_agent() -> ImageOverlayTextAgent:
    s = get_settings()
    llm = UsageTrackingLLMClient(
        GeminiClient(s.gemini_api_key, s.gemini_generation_model), get_usage_store(), purpose="image_overlay_text"
    )
    return ImageOverlayTextAgent(llm)


@lru_cache
def get_facts_store() -> ProjectFactsStore:
    return ProjectFactsStore(get_settings().project_data_path)


@lru_cache
def get_library_agent() -> ContentLibraryAgent:
    return ContentLibraryAgent(get_library_store())


@lru_cache
def get_insights_agent() -> InsightsAgent:
    return InsightsAgent(get_library_store(), get_asset_store())


@lru_cache
def get_orchestrator() -> Orchestrator:
    s = get_settings()
    usage_store = get_usage_store()
    embedding_client = UsageTrackingEmbeddingClient(
        GeminiEmbeddingClient(s.gemini_api_key, s.gemini_embedding_model), usage_store, purpose="embedding"
    )
    context_agent = ContextAgent(
        get_facts_store(),
        PineconeVectorStore(s.pinecone_api_key, s.pinecone_index_name, s.pinecone_embedding_dim),
        embedding_client,
        top_k=s.context_top_k,
    )
    asset_agent = AssetAgent(get_asset_store())
    llm = UsageTrackingLLMClient(
        GeminiClient(s.gemini_api_key, s.gemini_generation_model), usage_store, purpose="content_generation"
    )
    return Orchestrator(
        context_agent,
        asset_agent,
        EmailContentAgent(llm),
        WhatsAppContentAgent(llm),
        ComplianceAgent(),
        get_library_agent(),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/campaigns/run")
def run_campaign(request: CampaignRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.run(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # An unhandled exception here would skip CORSMiddleware's error path and
        # the browser would report it as an opaque CORS failure -- surface a real
        # message instead, since this is almost always a transient upstream
        # failure (Gemini/Pinecone rate limit or outage), not a client error.
        raise HTTPException(status_code=502, detail=f"Content generation failed: {e}")


class EmailDraftReview(BaseModel):
    draft: EmailDraft
    approved: bool
    issues: list[ComplianceIssue]


class WhatsAppDraftReview(BaseModel):
    draft: WhatsAppDraft
    approved: bool
    issues: list[ComplianceIssue]


class GenerateResponse(BaseModel):
    email: Optional[EmailDraftReview] = None
    whatsapp: Optional[WhatsAppDraftReview] = None


class ReviseEmailRequest(BaseModel):
    project_id: str
    campaign_brief: CampaignBrief
    email_brief: EmailBrief
    current_draft: EmailDraft
    instruction: str


class ReviseWhatsAppRequest(BaseModel):
    project_id: str
    campaign_brief: CampaignBrief
    whatsapp_brief: WhatsAppBrief
    current_draft: WhatsAppDraft
    instruction: str


class MoreSubjectLinesRequest(BaseModel):
    project_id: str
    campaign_brief: CampaignBrief
    existing_subject_lines: list[str]


class MoreSubjectLinesResponse(BaseModel):
    subject_lines: list[str]


class SaveEmailRequest(BaseModel):
    project_id: str
    campaign_id: str
    draft: EmailDraft
    template_name: str
    content_tag: ContentTag
    variant_label: str = "primary"
    as_draft: bool = False


class SaveWhatsAppRequest(BaseModel):
    project_id: str
    campaign_id: str
    draft: WhatsAppDraft
    template_name: str
    content_tag: ContentTag
    variant_label: str = "primary"
    as_draft: bool = False


class SaveResponse(BaseModel):
    creative_id: str


@app.post("/campaigns/generate", response_model=GenerateResponse)
def generate_campaign(request: CampaignRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    """Generates and compliance-checks drafts for every requested channel
    without saving anything -- pairs with /campaigns/revise/* and
    /content-library/* (save) so the caller can review and refine before
    anything lands in the library.
    """
    try:
        result = orchestrator.generate_drafts(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Content generation failed: {e}")
    return result


@app.post("/campaigns/revise/email", response_model=EmailDraftReview)
def revise_email(payload: ReviseEmailRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.revise_email(
            project_id=payload.project_id,
            campaign_brief=payload.campaign_brief,
            email_brief=payload.email_brief,
            current_draft=payload.current_draft,
            instruction=payload.instruction,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Revision failed: {e}")


@app.post("/campaigns/generate-more-subject-lines", response_model=MoreSubjectLinesResponse)
def generate_more_subject_lines(
    payload: MoreSubjectLinesRequest, orchestrator: Orchestrator = Depends(get_orchestrator)
):
    try:
        subject_lines = orchestrator.generate_more_subject_lines(
            project_id=payload.project_id,
            campaign_brief=payload.campaign_brief,
            existing_subject_lines=payload.existing_subject_lines,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Subject line generation failed: {e}")
    return {"subject_lines": subject_lines}


@app.post("/campaigns/revise/whatsapp", response_model=WhatsAppDraftReview)
def revise_whatsapp(payload: ReviseWhatsAppRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        return orchestrator.revise_whatsapp(
            project_id=payload.project_id,
            campaign_brief=payload.campaign_brief,
            whatsapp_brief=payload.whatsapp_brief,
            current_draft=payload.current_draft,
            instruction=payload.instruction,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Revision failed: {e}")


@app.post("/content-library/email", response_model=SaveResponse)
def save_email(payload: SaveEmailRequest, library_agent: ContentLibraryAgent = Depends(get_library_agent)):
    creative_id = library_agent.save(
        project_id=payload.project_id,
        campaign_id=payload.campaign_id,
        channel=Channel.EMAIL,
        variant_label=payload.variant_label,
        template_name=payload.template_name,
        content_tag=payload.content_tag.value,
        content=payload.draft,
        asset_ids=payload.draft.referenced_asset_ids,
        status=ContentStatus.DRAFT if payload.as_draft else ContentStatus.APPROVED,
    )
    return {"creative_id": creative_id}


@app.post("/content-library/whatsapp", response_model=SaveResponse)
def save_whatsapp(payload: SaveWhatsAppRequest, library_agent: ContentLibraryAgent = Depends(get_library_agent)):
    asset_ids = [payload.draft.image_asset_id] if payload.draft.image_asset_id else []
    creative_id = library_agent.save(
        project_id=payload.project_id,
        campaign_id=payload.campaign_id,
        channel=Channel.WHATSAPP,
        variant_label=payload.variant_label,
        template_name=payload.template_name,
        content_tag=payload.content_tag.value,
        content=payload.draft,
        asset_ids=asset_ids,
        status=ContentStatus.DRAFT if payload.as_draft else ContentStatus.APPROVED,
    )
    return {"creative_id": creative_id}


@app.get("/content-library/{creative_id}", response_model=ContentLibraryEntry)
def get_content(creative_id: str, store: ContentLibraryStore = Depends(get_library_store)):
    entry = store.get(creative_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No content found for creative_id '{creative_id}'")
    return entry


@app.delete("/content-library/{creative_id}", status_code=204)
def delete_content(creative_id: str, library_agent: ContentLibraryAgent = Depends(get_library_agent)):
    if not library_agent.delete(creative_id):
        raise HTTPException(status_code=404, detail=f"No content found for creative_id '{creative_id}'")


class RenameContentRequest(BaseModel):
    template_name: str


@app.patch("/content-library/{creative_id}", response_model=ContentLibraryEntry)
def rename_content(
    creative_id: str, payload: RenameContentRequest, library_agent: ContentLibraryAgent = Depends(get_library_agent)
):
    entry = library_agent.rename(creative_id, payload.template_name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No content found for creative_id '{creative_id}'")
    return entry


@app.get("/content-library/{creative_id}/sends", response_model=list[EmailSendRecord])
def list_email_sends(creative_id: str, store: EmailSendStore = Depends(get_email_send_store)):
    return store.list_for_creative(creative_id)


@app.get("/content-library", response_model=list[ContentLibraryEntry])
def list_content(
    project_id: str, channel: Optional[Channel] = None, store: ContentLibraryStore = Depends(get_library_store)
):
    return store.list_by_project(project_id, channel=channel)


@app.get("/projects", response_model=list[ProjectSummary])
def list_projects(facts_store: ProjectFactsStore = Depends(get_facts_store)):
    # Populates the project picker -- only projects with a facts.json (i.e.
    # actually usable for generation) show up here.
    return facts_store.list_projects()


@app.get("/assets", response_model=list[Asset])
def list_assets(project_id: str, store: LocalAssetStore = Depends(get_asset_store)):
    # Content-library entries only store asset_ids, not resolved URLs -- the
    # browse UI calls this to turn an id into something it can actually render.
    return store.list_for_project(project_id)


@app.get("/insights", response_model=ProjectInsights)
def get_insights(project_id: str, agent: InsightsAgent = Depends(get_insights_agent)):
    return agent.compute(project_id)


@app.get("/usage", response_model=UsageSummary)
def get_usage(store: UsageStore = Depends(get_usage_store)):
    return store.summary()


class SetUsageCapRequest(BaseModel):
    daily_cap: Optional[int] = None


@app.put("/usage/cap", response_model=UsageSummary)
def set_usage_cap(payload: SetUsageCapRequest, store: UsageStore = Depends(get_usage_store)):
    store.set_daily_cap(payload.daily_cap)
    return store.summary()


# Deliberately not pydantic's EmailStr (would need the extra email-validator
# dependency) -- this is a light sanity check, not the security boundary;
# a malformed address just fails at the real SMTP send instead.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    html_body: str
    # Set only when sending a saved library entry -- a send is logged
    # against this creative_id when present, and left unlogged for a
    # not-yet-saved draft preview (nothing to attach the record to).
    creative_id: Optional[str] = None


class SendEmailResponse(BaseModel):
    sent: bool


@app.post("/send-email", response_model=SendEmailResponse)
def send_email(
    payload: SendEmailRequest,
    sender: Optional[EmailSender] = Depends(get_email_sender),
    send_store: EmailSendStore = Depends(get_email_send_store),
):
    if sender is None:
        raise HTTPException(
            status_code=503,
            detail="Email sending isn't configured yet -- add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env",
        )
    if not _EMAIL_RE.match(payload.to):
        raise HTTPException(status_code=400, detail=f"'{payload.to}' doesn't look like a valid email address")
    try:
        sender.send(to=payload.to, subject=payload.subject, html_body=payload.html_body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
    if payload.creative_id:
        send_store.record(payload.creative_id, payload.to)
    return {"sent": True}


class SaveGeneratedAssetRequest(BaseModel):
    project_id: str
    image_base64: str = Field(..., description="PNG bytes, optionally prefixed with a data: URL header")
    tags: list[str] = Field(default_factory=list)


@app.post("/assets/generated", response_model=Asset)
def save_generated_asset(payload: SaveGeneratedAssetRequest, store: LocalAssetStore = Depends(get_asset_store)):
    raw = payload.image_base64.split(",", 1)[-1]  # strip a leading "data:image/png;base64," if present
    try:
        image_bytes = base64.b64decode(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")
    return store.save_generated_asset(payload.project_id, image_bytes, tags=payload.tags)


class SuggestOverlayTextRequest(BaseModel):
    campaign_brief: CampaignBrief


class SuggestOverlayTextResponse(BaseModel):
    suggestions: list[str]


@app.post("/assets/suggest-overlay-text", response_model=SuggestOverlayTextResponse)
def suggest_overlay_text(
    payload: SuggestOverlayTextRequest, agent: ImageOverlayTextAgent = Depends(get_image_text_agent)
):
    try:
        suggestions = agent.suggest(payload.campaign_brief)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Suggestion failed: {e}")
    return {"suggestions": suggestions}


# Production only: one container serves both the API (every route above)
# and the built frontend, so the browser never needs cross-origin requests.
# Mounted last so it only catches paths no API route already claimed.
# frontend_dist doesn't exist in local dev (the frontend runs on its own
# Vite dev server there instead), so this is a no-op locally.
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend_dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
