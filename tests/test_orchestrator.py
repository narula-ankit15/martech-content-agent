from app.agents.asset_agent import AssetAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.context_agent import ContextAgent
from app.agents.email_agent import EmailContentAgent
from app.agents.library_agent import ContentLibraryAgent
from app.agents.orchestrator import Orchestrator
from app.agents.whatsapp_agent import WhatsAppContentAgent
from app.models import (
    Asset,
    AudienceTone,
    CampaignBrief,
    CampaignRequest,
    EmailBrief,
    ProjectFacts,
    Purpose,
    RetrievedChunk,
    WhatsAppBrief,
)
from app.storage.content_library_store import ContentLibraryStore


class RoutingFakeLLMClient:
    """Returns a different canned response depending on which content
    agent is calling (email vs whatsapp), matched by a keyword unique to
    each agent's system prompt -- lets one fake drive the whole orchestrator
    test without hitting Gemini.
    """

    def generate_json(self, *, system: str, prompt: str) -> dict:
        if "email" in system.lower():
            return {
                "subject_lines": ["Come see Skyline Heights", "Book your visit"],
                "html_body": "<p>Come see Skyline Heights this weekend.</p>",
                "referenced_asset_ids": [],
            }
        return {
            "message_variants": ["Come see Skyline Heights this weekend!", "Skyline Heights is waiting for you!"],
            "cta_variants": ["Book now", "Book now"],
            "image_asset_id": None,
        }


class FakeFactsStore:
    def get(self, project_id: str) -> ProjectFacts:
        return ProjectFacts(project_name="Skyline Heights", rera_number="P51700012345")


class FakeVectorStore:
    def query(self, *, project_id: str, embedding, top_k: int):
        return [RetrievedChunk(text="Skyline Heights riverside homes.", source="brochure.pdf", score=0.9)]


class FakeEmbeddingClient:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeAssetStore:
    def list_for_project(self, project_id: str) -> list:
        return [
            Asset(asset_id="a1", project_id=project_id, url="https://cdn/a1.jpg", kind="image", tags=["exterior"]),
            Asset(asset_id="a2", project_id=project_id, url="https://cdn/a2.jpg", kind="image", tags=["interior"]),
        ]


def _build_orchestrator(tmp_path) -> Orchestrator:
    context_agent = ContextAgent(FakeFactsStore(), FakeVectorStore(), FakeEmbeddingClient(), top_k=3)
    asset_agent = AssetAgent(FakeAssetStore())
    llm = RoutingFakeLLMClient()
    email_agent = EmailContentAgent(llm)
    whatsapp_agent = WhatsAppContentAgent(llm)
    compliance_agent = ComplianceAgent()
    library_agent = ContentLibraryAgent(ContentLibraryStore(str(tmp_path / "content_library.db")))
    return Orchestrator(context_agent, asset_agent, email_agent, whatsapp_agent, compliance_agent, library_agent)


def _campaign_brief() -> CampaignBrief:
    return CampaignBrief(
        purpose=Purpose.PROMO_SALE,
        key_message="drive site visits",
        cta_text="Book a visit",
        audience_tone=AudienceTone.CONSUMERS_PREMIUM,
    )


def test_orchestrator_runs_both_channels_and_saves_approved_drafts(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    request = CampaignRequest(
        campaign_id="camp-001",
        project_id="proj-skyline",
        campaign_brief=_campaign_brief(),
        email_brief=EmailBrief(),
        whatsapp_brief=WhatsAppBrief(),
    )

    result = orchestrator.run(request)

    assert set(result["creative_ids"].keys()) == {"email", "whatsapp"}
    assert result["creative_ids"]["email"].startswith("proj-skyline-email-camp-001-")
    assert result["creative_ids"]["whatsapp"].startswith("proj-skyline-whatsapp-camp-001-")
    # RERA disclaimer was missing from both fake drafts -- compliance should
    # have auto-fixed it (approved) rather than rejecting.
    assert any("missing_rera_disclaimer" in note for note in result["status_notes"])


def test_orchestrator_only_runs_requested_channel(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    request = CampaignRequest(
        campaign_id="camp-002",
        project_id="proj-skyline",
        campaign_brief=_campaign_brief(),
        email_brief=EmailBrief(),
    )

    result = orchestrator.run(request)

    assert list(result["creative_ids"].keys()) == ["email"]


def test_generate_drafts_does_not_save_to_library(tmp_path):
    store = ContentLibraryStore(str(tmp_path / "content_library.db"))
    context_agent = ContextAgent(FakeFactsStore(), FakeVectorStore(), FakeEmbeddingClient(), top_k=3)
    asset_agent = AssetAgent(FakeAssetStore())
    llm = RoutingFakeLLMClient()
    orchestrator = Orchestrator(
        context_agent,
        asset_agent,
        EmailContentAgent(llm),
        WhatsAppContentAgent(llm),
        ComplianceAgent(),
        ContentLibraryAgent(store),
    )
    request = CampaignRequest(
        campaign_id="camp-003",
        project_id="proj-skyline",
        campaign_brief=_campaign_brief(),
        email_brief=EmailBrief(),
        whatsapp_brief=WhatsAppBrief(),
    )

    result = orchestrator.generate_drafts(request)

    assert set(result.keys()) == {"email", "whatsapp"}
    assert result["email"]["approved"] is True  # RERA auto-fixed, not blocking
    assert "P51700012345" in result["email"]["draft"].html_body
    # the whole point: nothing gets persisted until an explicit save call
    assert store.list_by_project("proj-skyline") == []


class RevisingFakeLLMClient:
    """Returns the normal canned response for a first-pass generate, but a
    distinguishable response once the prompt shows this is a revise call
    (identified by the CURRENT DRAFT marker the agent's revise() adds).
    """

    def generate_json(self, *, system: str, prompt: str) -> dict:
        is_revise = "CURRENT DRAFT" in prompt
        if "email" in system.lower():
            if is_revise:
                return {
                    "subject_lines": ["Shorter subject"],
                    "html_body": "<p>Shorter revised body.</p>",
                    "referenced_asset_ids": [],
                }
            return {
                "subject_lines": ["Come see Skyline Heights", "Book your visit"],
                "html_body": "<p>Come see Skyline Heights this weekend.</p>",
                "referenced_asset_ids": [],
            }
        if is_revise:
            return {
                "message_variants": ["Shorter revised message!"],
                "cta_variants": ["Book now"],
                "image_asset_id": None,
            }
        return {
            "message_variants": ["Come see Skyline Heights this weekend!"],
            "cta_variants": ["Book now"],
            "image_asset_id": None,
        }


def test_revise_email_applies_instruction_without_saving(tmp_path):
    store = ContentLibraryStore(str(tmp_path / "content_library.db"))
    context_agent = ContextAgent(FakeFactsStore(), FakeVectorStore(), FakeEmbeddingClient(), top_k=3)
    asset_agent = AssetAgent(FakeAssetStore())
    llm = RevisingFakeLLMClient()
    orchestrator = Orchestrator(
        context_agent,
        asset_agent,
        EmailContentAgent(llm),
        WhatsAppContentAgent(llm),
        ComplianceAgent(),
        ContentLibraryAgent(store),
    )
    campaign_brief = _campaign_brief()
    original = orchestrator.generate_drafts(
        CampaignRequest(
            campaign_id="camp-004", project_id="proj-skyline", campaign_brief=campaign_brief, email_brief=EmailBrief()
        )
    )["email"]["draft"]

    revised = orchestrator.revise_email(
        project_id="proj-skyline",
        campaign_brief=campaign_brief,
        email_brief=EmailBrief(),
        current_draft=original,
        instruction="make it shorter",
    )

    assert revised["draft"].subject_lines == ["Shorter subject"]
    assert "Shorter revised body" in revised["draft"].html_body
    assert store.list_by_project("proj-skyline") == []


def test_revise_whatsapp_applies_instruction_without_saving(tmp_path):
    store = ContentLibraryStore(str(tmp_path / "content_library.db"))
    context_agent = ContextAgent(FakeFactsStore(), FakeVectorStore(), FakeEmbeddingClient(), top_k=3)
    asset_agent = AssetAgent(FakeAssetStore())
    llm = RevisingFakeLLMClient()
    orchestrator = Orchestrator(
        context_agent,
        asset_agent,
        EmailContentAgent(llm),
        WhatsAppContentAgent(llm),
        ComplianceAgent(),
        ContentLibraryAgent(store),
    )
    campaign_brief = _campaign_brief()
    original = orchestrator.generate_drafts(
        CampaignRequest(
            campaign_id="camp-005",
            project_id="proj-skyline",
            campaign_brief=campaign_brief,
            whatsapp_brief=WhatsAppBrief(),
        )
    )["whatsapp"]["draft"]

    revised = orchestrator.revise_whatsapp(
        project_id="proj-skyline",
        campaign_brief=campaign_brief,
        whatsapp_brief=WhatsAppBrief(),
        current_draft=original,
        instruction="make it shorter",
    )

    assert "Shorter revised message!" in revised["draft"].message_variants[0]
    assert store.list_by_project("proj-skyline") == []


def test_generate_more_subject_lines_returns_new_lines_only(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)

    more = orchestrator.generate_more_subject_lines(
        project_id="proj-skyline",
        campaign_brief=_campaign_brief(),
        existing_subject_lines=["Come see Skyline Heights", "Book your visit"],
    )

    assert more == ["Come see Skyline Heights", "Book your visit"]


def test_email_candidate_assets_uses_selected_ids_in_order_when_given(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    email_brief = EmailBrief(selected_asset_ids=["a2", "a1"])

    assets = orchestrator._email_candidate_assets("proj-skyline", _campaign_brief(), email_brief)

    assert [a.asset_id for a in assets] == ["a2", "a1"]


def test_email_candidate_assets_falls_back_to_tag_search_when_none_selected(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    email_brief = EmailBrief()

    assets = orchestrator._email_candidate_assets("proj-skyline", _campaign_brief(), email_brief)

    assert {a.asset_id for a in assets} == {"a1", "a2"}


def test_whatsapp_candidate_assets_uses_selected_id_when_given(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    whatsapp_brief = WhatsAppBrief(selected_asset_id="a2")

    assets = orchestrator._whatsapp_candidate_assets("proj-skyline", _campaign_brief(), whatsapp_brief)

    assert [a.asset_id for a in assets] == ["a2"]


def test_whatsapp_candidate_assets_falls_back_to_tag_search_when_none_selected(tmp_path):
    orchestrator = _build_orchestrator(tmp_path)
    whatsapp_brief = WhatsAppBrief()

    assets = orchestrator._whatsapp_candidate_assets("proj-skyline", _campaign_brief(), whatsapp_brief)

    assert {a.asset_id for a in assets} == {"a1", "a2"}
