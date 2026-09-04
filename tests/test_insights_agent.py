from app.agents.insights_agent import InsightsAgent
from app.agents.library_agent import ContentLibraryAgent
from app.models import Asset, Channel, EmailDraft, WhatsAppDraft
from app.storage.content_library_store import ContentLibraryStore


class FakeAssetStore:
    def __init__(self, assets: list[Asset]):
        self._assets = assets

    def list_for_project(self, project_id: str) -> list[Asset]:
        return [a for a in self._assets if a.project_id == project_id]


def _build_agent(tmp_path, assets: list[Asset] = ()):
    store = ContentLibraryStore(str(tmp_path / "content_library.db"))
    library_agent = ContentLibraryAgent(store)
    insights_agent = InsightsAgent(store, FakeAssetStore(list(assets)))
    return library_agent, insights_agent


def test_email_insights_on_empty_project_are_all_zero(tmp_path):
    _, insights_agent = _build_agent(tmp_path)

    result = insights_agent.compute("proj-empty")

    assert result.email.count == 0
    assert result.email.avg_subject_words == 0.0
    assert result.email.emoji_usage_rate == 0.0
    assert result.email.top_words == []
    assert result.email.image_usage_rate == 0.0
    assert result.email.content_tag_distribution == {}


def test_email_insights_compute_length_emoji_and_words(tmp_path):
    library_agent, insights_agent = _build_agent(tmp_path)
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-1",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(
            subject_lines=["Book your dream home today", "Limited offer ✨ ends soon"],
            html_body="<p>hi</p>",
            referenced_asset_ids=[],
        ),
        asset_ids=[],
        content_tag="promotional_communication",
    )
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-2",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Your dream possession update"], html_body="<p>hi</p>", referenced_asset_ids=[]),
        asset_ids=[],
        content_tag="service",
    )

    result = insights_agent.compute("proj-x")

    assert result.email.count == 2
    # 3 subject lines total: "Book your dream home today" (5 words), "Limited
    # offer ✨ ends soon" (5 words incl. the emoji token), "Your dream
    # possession update" (4 words) -> avg = 14/3
    assert result.email.avg_subject_words == round(14 / 3, 1)
    assert result.email.emoji_usage_rate == round(1 / 3, 2)
    words = {w.word: w.count for w in result.email.top_words}
    assert words["dream"] == 2
    assert result.email.content_tag_distribution == {"promotional_communication": 1, "service": 1}


def test_email_insights_image_usage_and_top_asset_tags(tmp_path):
    assets = [
        Asset(asset_id="a1", project_id="proj-x", url="https://cdn/a1.jpg", kind="image", tags=["exterior", "tower"]),
        Asset(asset_id="a2", project_id="proj-x", url="https://cdn/a2.jpg", kind="image", tags=["exterior", "pool"]),
    ]
    library_agent, insights_agent = _build_agent(tmp_path, assets)
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-1",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>", referenced_asset_ids=["a1", "a2"]),
        asset_ids=["a1", "a2"],
    )
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-2",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>", referenced_asset_ids=[]),
        asset_ids=[],
    )

    result = insights_agent.compute("proj-x")

    assert result.email.image_usage_rate == 0.5
    tags = {t.tag: t.count for t in result.email.top_asset_tags}
    assert tags["exterior"] == 2
    assert tags["tower"] == 1
    assert tags["pool"] == 1


def test_whatsapp_insights_compute_length_and_cta_frequency(tmp_path):
    library_agent, insights_agent = _build_agent(tmp_path)
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-1",
        channel=Channel.WHATSAPP,
        variant_label="primary",
        content=WhatsAppDraft(
            message_variants=["Book a site visit this weekend", "Visit us this weekend for offers"],
            cta_variants=["Book a site visit", "Book a site visit"],
            image_asset_id=None,
        ),
        asset_ids=[],
    )
    library_agent.save(
        project_id="proj-x",
        campaign_id="camp-2",
        channel=Channel.WHATSAPP,
        variant_label="primary",
        content=WhatsAppDraft(message_variants=["Call now for details"], cta_variants=["Call now"], image_asset_id="a1"),
        asset_ids=["a1"],
    )

    result = insights_agent.compute("proj-x")

    assert result.whatsapp.count == 2
    assert result.whatsapp.image_usage_rate == 0.5
    ctas = {c.cta: c.count for c in result.whatsapp.top_cta_phrases}
    assert ctas["Book a site visit"] == 2
    assert ctas["Call now"] == 1


def test_insights_only_considers_the_given_project(tmp_path):
    library_agent, insights_agent = _build_agent(tmp_path)
    library_agent.save(
        project_id="proj-other",
        campaign_id="camp-1",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=EmailDraft(subject_lines=["Not this project"], html_body="<p>hi</p>", referenced_asset_ids=[]),
        asset_ids=[],
    )

    result = insights_agent.compute("proj-x")

    assert result.email.count == 0
    assert result.whatsapp.count == 0
