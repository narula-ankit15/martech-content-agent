import pytest

from app.models import (
    Asset,
    AudienceTone,
    CampaignBrief,
    EmailBrief,
    ProjectContext,
    ProjectFacts,
    Purpose,
    RetrievedChunk,
    WhatsAppBrief,
)


@pytest.fixture
def sample_campaign_brief() -> CampaignBrief:
    return CampaignBrief(
        purpose=Purpose.PROMO_SALE,
        key_message="drive site visits for the 3BHK launch",
        cta_text="Book a site visit",
        audience_tone=AudienceTone.CONSUMERS_PREMIUM,
    )


@pytest.fixture
def sample_email_brief() -> EmailBrief:
    return EmailBrief()


@pytest.fixture
def sample_whatsapp_brief() -> WhatsAppBrief:
    return WhatsAppBrief(cta_required=True, image_required=True)


@pytest.fixture
def sample_context() -> ProjectContext:
    facts = ProjectFacts(
        project_name="Skyline Heights",
        rera_number="P51700012345",
        unit_configs=["2BHK", "3BHK"],
        price_bands={"3BHK": "1.4Cr - 1.7Cr"},
        possession_date="Dec 2027",
        usps=["Riverside view", "5-min from metro"],
        amenities=["Clubhouse", "Infinity pool"],
        location="Bandra East, Mumbai",
    )
    return ProjectContext(
        project_id="proj-skyline",
        facts=facts,
        retrieved_chunks=[
            RetrievedChunk(text="Skyline Heights offers riverside 3BHK homes.", source="brochure.pdf", score=0.91)
        ],
    )


@pytest.fixture
def sample_assets() -> list[Asset]:
    return [
        Asset(asset_id="asset-clubhouse-1", project_id="proj-skyline", url="https://cdn/clubhouse.jpg", kind="image", tags=["clubhouse"]),
        Asset(asset_id="asset-3bhk-1", project_id="proj-skyline", url="https://cdn/3bhk.jpg", kind="image", tags=["3bhk", "interior"]),
    ]
