import pytest
from fastapi.testclient import TestClient

import base64

from app.agents.insights_agent import InsightsAgent
from app.agents.library_agent import ContentLibraryAgent
from app.api.main import (
    app,
    get_asset_store,
    get_email_send_store,
    get_email_sender,
    get_facts_store,
    get_image_text_agent,
    get_insights_agent,
    get_library_agent,
    get_library_store,
    get_orchestrator,
    get_usage_store,
)
from app.models import Asset, CampaignRequest, Channel, EmailDraft, ProjectSummary, WhatsAppDraft
from app.storage.content_library_store import ContentLibraryStore
from app.storage.email_send_store import EmailSendStore
from app.storage.usage_store import UsageStore


class FakeOrchestrator:
    def __init__(self):
        self.last_request = None
        self.last_revise_call = None

    def run(self, request: CampaignRequest):
        self.last_request = request
        if request.project_id == "proj-boom":
            raise RuntimeError("503 UNAVAILABLE: upstream model overloaded")
        return {"creative_ids": {"email": "proj-x-email-camp-x-abc123"}, "status_notes": ["email: approved"]}

    def generate_drafts(self, request: CampaignRequest):
        self.last_request = request
        result = {}
        if request.email_brief is not None:
            result["email"] = {
                "draft": EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>", referenced_asset_ids=[]),
                "approved": True,
                "issues": [],
            }
        if request.whatsapp_brief is not None:
            result["whatsapp"] = {
                "draft": WhatsAppDraft(message_variants=["Hi there"], cta_variants=["Book now"], image_asset_id=None),
                "approved": True,
                "issues": [],
            }
        return result

    def revise_email(self, **kwargs):
        self.last_revise_call = kwargs
        return {
            "draft": EmailDraft(subject_lines=["Shorter"], html_body="<p>shorter</p>", referenced_asset_ids=[]),
            "approved": True,
            "issues": [],
        }

    def revise_whatsapp(self, **kwargs):
        self.last_revise_call = kwargs
        return {
            "draft": WhatsAppDraft(message_variants=["Shorter message"], cta_variants=["Book now"], image_asset_id=None),
            "approved": True,
            "issues": [],
        }

    def generate_more_subject_lines(self, **kwargs):
        self.last_revise_call = kwargs
        return ["A fresh angle 🏡", "Another new hook ✨"]


class FakeAssetStore:
    def __init__(self):
        self.last_save_call = None

    def list_for_project(self, project_id: str) -> list:
        return [Asset(asset_id="a1", project_id=project_id, url="https://cdn/a1.jpg", kind="image", tags=["pool"])]

    def save_generated_asset(self, project_id: str, image_bytes: bytes, tags: list) -> Asset:
        self.last_save_call = {"project_id": project_id, "image_bytes": image_bytes, "tags": tags}
        return Asset(
            asset_id="proj-x-img-template-abc123",
            project_id=project_id,
            url="http://127.0.0.1:8123/asset-files/proj-x/generated/proj-x-img-template-abc123.png",
            kind="image",
            tags=tags,
            width=64,
            height=32,
        )


class FakeImageTextAgent:
    def __init__(self):
        self.last_campaign_brief = None

    def suggest(self, campaign_brief) -> list:
        self.last_campaign_brief = campaign_brief
        return ["Book Your 3BHK Today", "Limited Units Left"]


class FakeEmailSender:
    def __init__(self, error: Exception = None):
        self.last_call = None
        self._error = error

    def send(self, *, to: str, subject: str, html_body: str) -> None:
        if self._error:
            raise self._error
        self.last_call = {"to": to, "subject": subject, "html_body": html_body}


class FakeFactsStore:
    def list_projects(self) -> list:
        return [
            ProjectSummary(project_id="crown-greens", project_name="The Crown Greens"),
            ProjectSummary(project_id="proj-skyline", project_name="Skyline Heights"),
        ]


@pytest.fixture
def client(tmp_path):
    store = ContentLibraryStore(str(tmp_path / "content_library.db"))
    usage_store = UsageStore(str(tmp_path / "usage.db"))
    # Shares the content_library.db file/path, matching how EmailSendStore
    # is wired in production (get_email_send_store reuses content_library_db_path).
    email_send_store = EmailSendStore(str(tmp_path / "content_library.db"))
    fake_orchestrator = FakeOrchestrator()
    fake_asset_store = FakeAssetStore()
    fake_image_text_agent = FakeImageTextAgent()

    app.dependency_overrides[get_library_store] = lambda: store
    app.dependency_overrides[get_library_agent] = lambda: ContentLibraryAgent(store)
    app.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator
    app.dependency_overrides[get_asset_store] = lambda: fake_asset_store
    app.dependency_overrides[get_facts_store] = lambda: FakeFactsStore()
    app.dependency_overrides[get_image_text_agent] = lambda: fake_image_text_agent
    app.dependency_overrides[get_insights_agent] = lambda: InsightsAgent(store, fake_asset_store)
    app.dependency_overrides[get_usage_store] = lambda: usage_store
    # Defaults to "not configured", matching a real deployment with no
    # GMAIL_ADDRESS/GMAIL_APP_PASSWORD set -- individual tests override this
    # with a FakeEmailSender when they need a "configured" sender.
    app.dependency_overrides[get_email_sender] = lambda: None
    app.dependency_overrides[get_email_send_store] = lambda: email_send_store
    test_client = TestClient(app)
    # Attached rather than added to the yielded tuple so every existing
    # `test_client, _, _ = client` call site keeps working unchanged.
    test_client.fake_asset_store = fake_asset_store
    test_client.fake_image_text_agent = fake_image_text_agent
    yield test_client, store, fake_orchestrator
    app.dependency_overrides.clear()


def test_health(client):
    test_client, _, _ = client
    resp = test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _campaign_brief_payload():
    return {
        "purpose": "promo_sale",
        "key_message": "drive visits",
        "cta_text": "Book a visit",
        "audience_tone": "consumers_premium",
    }


def test_run_campaign_returns_creative_ids(client):
    test_client, _, fake_orchestrator = client
    payload = {
        "campaign_id": "camp-x",
        "project_id": "proj-x",
        "campaign_brief": _campaign_brief_payload(),
        "email_brief": {},
    }
    resp = test_client.post("/campaigns/run", json=payload)
    assert resp.status_code == 200
    assert resp.json()["creative_ids"] == {"email": "proj-x-email-camp-x-abc123"}
    assert fake_orchestrator.last_request.project_id == "proj-x"


def test_run_campaign_missing_channel_briefs_returns_422(client):
    test_client, _, _ = client
    payload = {"campaign_id": "camp-x", "project_id": "proj-x", "campaign_brief": _campaign_brief_payload()}
    resp = test_client.post("/campaigns/run", json=payload)
    assert resp.status_code == 422


def test_run_campaign_upstream_failure_returns_502_with_cors_headers(client):
    test_client, _, _ = client
    payload = {
        "campaign_id": "camp-x",
        "project_id": "proj-boom",
        "campaign_brief": _campaign_brief_payload(),
        "email_brief": {},
    }
    resp = test_client.post(
        "/campaigns/run", json=payload, headers={"Origin": "http://localhost:5174"}
    )
    assert resp.status_code == 502
    assert "upstream model overloaded" in resp.json()["detail"]
    # This is what a raw unhandled exception would fail to include, which is
    # what makes the browser report it as an opaque "CORS error" instead.
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5174"


def test_get_content_by_creative_id(client):
    test_client, store, _ = client
    from app.agents.library_agent import ContentLibraryAgent

    creative_id = ContentLibraryAgent(store).save(
        project_id="proj-x",
        campaign_id="camp-x",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"),
        asset_ids=[],
    )

    resp = test_client.get(f"/content-library/{creative_id}")
    assert resp.status_code == 200
    assert resp.json()["creative_id"] == creative_id


def test_get_content_missing_creative_id_returns_404(client):
    test_client, _, _ = client
    resp = test_client.get("/content-library/does-not-exist")
    assert resp.status_code == 404


def test_delete_content_removes_entry(client):
    test_client, store, _ = client
    from app.agents.library_agent import ContentLibraryAgent

    creative_id = ContentLibraryAgent(store).save(
        project_id="proj-x",
        campaign_id="camp-x",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"),
        asset_ids=[],
    )

    resp = test_client.delete(f"/content-library/{creative_id}")
    assert resp.status_code == 204
    assert store.get(creative_id) is None


def test_delete_content_missing_creative_id_returns_404(client):
    test_client, _, _ = client
    resp = test_client.delete("/content-library/does-not-exist")
    assert resp.status_code == 404


def test_rename_content_updates_template_name(client):
    test_client, store, _ = client
    from app.agents.library_agent import ContentLibraryAgent

    creative_id = ContentLibraryAgent(store).save(
        project_id="proj-x",
        campaign_id="camp-x",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"),
        asset_ids=[],
        template_name="Original Name",
    )

    resp = test_client.patch(f"/content-library/{creative_id}", json={"template_name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["template_name"] == "New Name"
    assert store.get(creative_id).template_name == "New Name"


def test_rename_content_missing_creative_id_returns_404(client):
    test_client, _, _ = client
    resp = test_client.patch("/content-library/does-not-exist", json={"template_name": "New Name"})
    assert resp.status_code == 404


def test_list_content_by_project(client):
    test_client, store, _ = client
    from app.agents.library_agent import ContentLibraryAgent

    agent = ContentLibraryAgent(store)
    agent.save(
        project_id="proj-x", campaign_id="camp-x", channel=Channel.EMAIL,
        variant_label="primary", content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"), asset_ids=[],
    )

    resp = test_client.get("/content-library", params={"project_id": "proj-x"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_generate_campaign_returns_drafts_without_saving(client):
    test_client, store, _ = client
    payload = {
        "campaign_id": "camp-x",
        "project_id": "proj-x",
        "campaign_brief": _campaign_brief_payload(),
        "email_brief": {},
        "whatsapp_brief": {},
    }
    resp = test_client.post("/campaigns/generate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"]["draft"]["subject_lines"] == ["Hi"]
    assert body["whatsapp"]["draft"]["message_variants"][0] == "Hi there"
    # generation must not have touched the library
    assert store.list_by_project("proj-x") == []


def test_revise_email_returns_updated_draft(client):
    test_client, _, fake_orchestrator = client
    payload = {
        "project_id": "proj-x",
        "campaign_brief": _campaign_brief_payload(),
        "email_brief": {},
        "current_draft": {"subject_lines": ["Original"], "html_body": "<p>original</p>", "referenced_asset_ids": []},
        "instruction": "make it shorter",
    }
    resp = test_client.post("/campaigns/revise/email", json=payload)
    assert resp.status_code == 200
    assert resp.json()["draft"]["subject_lines"] == ["Shorter"]
    assert fake_orchestrator.last_revise_call["instruction"] == "make it shorter"


def test_revise_whatsapp_returns_updated_draft(client):
    test_client, _, _ = client
    payload = {
        "project_id": "proj-x",
        "campaign_brief": _campaign_brief_payload(),
        "whatsapp_brief": {},
        "current_draft": {"message_variants": ["Original message"], "cta_variants": ["Book now"], "image_asset_id": None},
        "instruction": "make it shorter",
    }
    resp = test_client.post("/campaigns/revise/whatsapp", json=payload)
    assert resp.status_code == 200
    assert resp.json()["draft"]["message_variants"][0] == "Shorter message"


def test_generate_more_subject_lines_returns_new_lines(client):
    test_client, _, fake_orchestrator = client
    payload = {
        "project_id": "proj-x",
        "campaign_brief": _campaign_brief_payload(),
        "existing_subject_lines": ["Original subject"],
    }
    resp = test_client.post("/campaigns/generate-more-subject-lines", json=payload)
    assert resp.status_code == 200
    assert resp.json()["subject_lines"] == ["A fresh angle 🏡", "Another new hook ✨"]
    assert fake_orchestrator.last_revise_call["existing_subject_lines"] == ["Original subject"]


def test_save_email_persists_to_library(client):
    test_client, store, _ = client
    payload = {
        "project_id": "proj-x",
        "campaign_id": "camp-x",
        "draft": {"subject_lines": ["Hi"], "html_body": "<p>hi</p>", "referenced_asset_ids": ["a1"]},
        "template_name": "Launch Announcement",
        "content_tag": "promotional_communication",
    }
    resp = test_client.post("/content-library/email", json=payload)
    assert resp.status_code == 200
    creative_id = resp.json()["creative_id"]
    assert creative_id.startswith("proj-x-email-camp-x-")

    saved = store.get(creative_id)
    assert saved is not None
    assert saved.content_json["subject_lines"] == ["Hi"]
    assert saved.asset_ids == ["a1"]
    assert saved.status.value == "approved"
    assert saved.template_name == "Launch Announcement"
    assert saved.content_tag == "promotional_communication"


def test_save_email_as_draft_persists_with_draft_status(client):
    test_client, store, _ = client
    payload = {
        "project_id": "proj-x",
        "campaign_id": "camp-x",
        "draft": {"subject_lines": ["Hi"], "html_body": "<p>hi</p>", "referenced_asset_ids": []},
        "template_name": "Launch Announcement",
        "content_tag": "service",
        "as_draft": True,
    }
    resp = test_client.post("/content-library/email", json=payload)
    assert resp.status_code == 200
    saved = store.get(resp.json()["creative_id"])
    assert saved.status.value == "draft"


def test_save_whatsapp_persists_to_library(client):
    test_client, store, _ = client
    payload = {
        "project_id": "proj-x",
        "campaign_id": "camp-x",
        "draft": {"message_variants": ["Hi there"], "cta_variants": ["Book now"], "image_asset_id": "a1"},
        "template_name": "Site Visit Nudge",
        "content_tag": "service",
    }
    resp = test_client.post("/content-library/whatsapp", json=payload)
    assert resp.status_code == 200
    creative_id = resp.json()["creative_id"]

    saved = store.get(creative_id)
    assert saved is not None
    assert saved.content_json["message_variants"][0] == "Hi there"
    assert saved.asset_ids == ["a1"]
    assert saved.status.value == "approved"
    assert saved.template_name == "Site Visit Nudge"
    assert saved.content_tag == "service"


def test_save_whatsapp_as_draft_persists_with_draft_status(client):
    test_client, store, _ = client
    payload = {
        "project_id": "proj-x",
        "campaign_id": "camp-x",
        "draft": {"message_variants": ["Hi there"], "cta_variants": ["Book now"], "image_asset_id": None},
        "template_name": "Site Visit Nudge",
        "content_tag": "promotional_communication",
        "as_draft": True,
    }
    resp = test_client.post("/content-library/whatsapp", json=payload)
    assert resp.status_code == 200
    saved = store.get(resp.json()["creative_id"])
    assert saved.status.value == "draft"


def test_list_assets(client):
    test_client, _, _ = client
    resp = test_client.get("/assets", params={"project_id": "proj-x"})
    assert resp.status_code == 200
    assert resp.json()[0]["asset_id"] == "a1"
    assert resp.json()[0]["url"] == "https://cdn/a1.jpg"


def test_list_projects(client):
    test_client, _, _ = client
    resp = test_client.get("/projects")
    assert resp.status_code == 200
    assert resp.json() == [
        {"project_id": "crown-greens", "project_name": "The Crown Greens"},
        {"project_id": "proj-skyline", "project_name": "Skyline Heights"},
    ]


def test_get_insights_returns_composition_analytics_for_saved_content(client):
    test_client, _, _ = client
    test_client.post(
        "/content-library/email",
        json={
            "project_id": "proj-x",
            "campaign_id": "camp-1",
            "draft": {"subject_lines": ["Book your dream home today ✨"], "html_body": "<p>hi</p>", "referenced_asset_ids": []},
            "template_name": "Test Email",
            "content_tag": "promotional_communication",
        },
    )

    resp = test_client.get("/insights", params={"project_id": "proj-x"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == "proj-x"
    assert body["email"]["count"] == 1
    assert body["email"]["emoji_usage_rate"] == 1.0
    assert body["whatsapp"]["count"] == 0


def test_get_usage_on_empty_store_is_zero(client):
    test_client, _, _ = client
    resp = test_client.get("/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "requests_today": 0,
        "rate_limited_today": False,
        "daily_cap": None,
        "remaining_today": None,
        "requests_by_purpose": {},
        "last_request_at": None,
    }


def test_set_usage_cap_then_get_usage_reflects_it(client):
    test_client, _, _ = client
    resp = test_client.put("/usage/cap", json={"daily_cap": 100})
    assert resp.status_code == 200
    assert resp.json()["daily_cap"] == 100
    assert resp.json()["remaining_today"] == 100

    resp = test_client.get("/usage")
    assert resp.json()["daily_cap"] == 100


def test_set_usage_cap_to_null_clears_it(client):
    test_client, _, _ = client
    test_client.put("/usage/cap", json={"daily_cap": 50})
    resp = test_client.put("/usage/cap", json={"daily_cap": None})
    assert resp.json()["daily_cap"] is None
    assert resp.json()["remaining_today"] is None


def test_save_generated_asset_returns_new_asset(client):
    test_client, _, _ = client
    tiny_png_base64 = base64.b64encode(b"not-real-png-bytes-but-fine-for-a-fake-store").decode()
    resp = test_client.post(
        "/assets/generated",
        json={"project_id": "proj-x", "image_base64": f"data:image/png;base64,{tiny_png_base64}", "tags": ["image-template"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_id"] == "proj-x-img-template-abc123"
    assert body["tags"] == ["image-template"]
    assert test_client.fake_asset_store.last_save_call["project_id"] == "proj-x"
    assert test_client.fake_asset_store.last_save_call["tags"] == ["image-template"]


def test_save_generated_asset_rejects_invalid_base64(client):
    test_client, _, _ = client
    resp = test_client.post("/assets/generated", json={"project_id": "proj-x", "image_base64": "%%%not-base64%%%", "tags": []})
    assert resp.status_code == 400


def test_suggest_overlay_text_returns_suggestions(client):
    test_client, _, _ = client
    resp = test_client.post("/assets/suggest-overlay-text", json={"campaign_brief": _campaign_brief_payload()})
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": ["Book Your 3BHK Today", "Limited Units Left"]}
    assert test_client.fake_image_text_agent.last_campaign_brief.key_message == "drive visits"


def test_send_email_returns_503_when_not_configured(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/send-email", json={"to": "recipient@example.com", "subject": "Hi", "html_body": "<p>hi</p>"}
    )
    assert resp.status_code == 503


def test_send_email_succeeds_when_configured(client):
    test_client, _, _ = client
    fake_sender = FakeEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: fake_sender

    resp = test_client.post(
        "/send-email",
        json={"to": "recipient@example.com", "subject": "Your dream home", "html_body": "<p>Hello</p>"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"sent": True}
    assert fake_sender.last_call == {
        "to": "recipient@example.com",
        "subject": "Your dream home",
        "html_body": "<p>Hello</p>",
    }


def test_send_email_rejects_malformed_address(client):
    test_client, _, _ = client
    app.dependency_overrides[get_email_sender] = lambda: FakeEmailSender()

    resp = test_client.post("/send-email", json={"to": "not-an-email", "subject": "Hi", "html_body": "<p>hi</p>"})

    assert resp.status_code == 400


def test_send_email_returns_502_when_sender_raises(client):
    test_client, _, _ = client
    app.dependency_overrides[get_email_sender] = lambda: FakeEmailSender(error=RuntimeError("SMTP AUTH failed"))

    resp = test_client.post(
        "/send-email", json={"to": "recipient@example.com", "subject": "Hi", "html_body": "<p>hi</p>"}
    )

    assert resp.status_code == 502


def test_send_email_with_creative_id_is_recorded_and_listable(client):
    test_client, _, _ = client
    app.dependency_overrides[get_email_sender] = lambda: FakeEmailSender()

    resp = test_client.post(
        "/send-email",
        json={
            "to": "buyer@example.com",
            "subject": "Hi",
            "html_body": "<p>hi</p>",
            "creative_id": "crown-greens-email-camp-1-abc123",
        },
    )
    assert resp.status_code == 200

    sends_resp = test_client.get("/content-library/crown-greens-email-camp-1-abc123/sends")
    assert sends_resp.status_code == 200
    records = sends_resp.json()
    assert len(records) == 1
    assert records[0]["to_email"] == "buyer@example.com"
    assert records[0]["sent_at"] is not None


def test_send_email_without_creative_id_is_not_recorded_anywhere(client):
    test_client, _, _ = client
    app.dependency_overrides[get_email_sender] = lambda: FakeEmailSender()

    resp = test_client.post(
        "/send-email", json={"to": "buyer@example.com", "subject": "Hi", "html_body": "<p>hi</p>"}
    )
    assert resp.status_code == 200

    # Nothing to look up by, but a send with no creative_id must not leak
    # into some other creative_id's history either.
    sends_resp = test_client.get("/content-library/some-other-creative-id/sends")
    assert sends_resp.json() == []


def test_send_email_failure_is_not_recorded(client):
    test_client, _, _ = client
    app.dependency_overrides[get_email_sender] = lambda: FakeEmailSender(error=RuntimeError("SMTP AUTH failed"))

    test_client.post(
        "/send-email",
        json={"to": "buyer@example.com", "subject": "Hi", "html_body": "<p>hi</p>", "creative_id": "creative-x"},
    )

    sends_resp = test_client.get("/content-library/creative-x/sends")
    assert sends_resp.json() == []


def test_list_email_sends_for_unknown_creative_id_is_empty(client):
    test_client, _, _ = client
    resp = test_client.get("/content-library/never-sent/sends")
    assert resp.status_code == 200
    assert resp.json() == []
