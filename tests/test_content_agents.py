from app.agents.email_agent import EmailContentAgent
from app.agents.whatsapp_agent import WhatsAppContentAgent
from app.models import EmailBrief, EmailImagery, WhatsAppBrief


class FakeLLMClient:
    """Returns a canned response and records the last prompt/system it was
    called with, so tests can assert on what the agent actually sent.
    """

    def __init__(self, response: dict):
        self._response = response
        self.last_system = None
        self.last_prompt = None

    def generate_json(self, *, system: str, prompt: str) -> dict:
        self.last_system = system
        self.last_prompt = prompt
        return self._response


def test_email_agent_parses_llm_response_into_draft(sample_campaign_brief, sample_email_brief, sample_context, sample_assets):
    fake_llm = FakeLLMClient(
        {
            "subject_lines": ["Your riverside 3BHK awaits", "Book a site visit this week"],
            "html_body": "<html><body>Skyline Heights, Bandra East</body></html>",
            "referenced_asset_ids": ["asset-3bhk-1"],
        }
    )
    agent = EmailContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        email_brief=sample_email_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert len(draft.subject_lines) == 2
    assert draft.referenced_asset_ids == ["asset-3bhk-1"]
    # facts the model must not hallucinate should actually reach the prompt
    assert "P51700012345" in fake_llm.last_prompt
    assert "1.4Cr - 1.7Cr" in fake_llm.last_prompt
    # cta_text lives on the shared campaign brief, not the email brief
    assert "Book a site visit" in fake_llm.last_prompt
    # the model doesn't know real asset URLs, so it must be told to use a
    # resolvable placeholder scheme instead of inventing a real-looking one
    assert "asset://{asset_id}" in fake_llm.last_prompt


def test_email_agent_instructs_model_to_use_selected_assets_in_order(
    sample_campaign_brief, sample_context, sample_assets
):
    brief_with_selection = EmailBrief(selected_asset_ids=["asset-3bhk-1", "asset-clubhouse-1"])
    fake_llm = FakeLLMClient(
        {"subject_lines": ["Hi", "Hello"], "html_body": "<p>hi</p>", "referenced_asset_ids": []}
    )
    agent = EmailContentAgent(fake_llm)

    # The orchestrator is responsible for resolving selected_asset_ids into
    # actual Asset objects (in that order) before calling generate() -- here
    # we simulate that by passing candidate_assets already reordered to match.
    reordered = [a for aid in brief_with_selection.selected_asset_ids for a in sample_assets if a.asset_id == aid]
    agent.generate(
        campaign_brief=sample_campaign_brief,
        email_brief=brief_with_selection,
        context=sample_context,
        candidate_assets=reordered,
    )

    assert "explicitly picked" in fake_llm.last_prompt
    assert "HERO/main image" in fake_llm.last_prompt
    assert "smaller supporting images" in fake_llm.last_prompt
    # the "pick assets whose tags best match" auto-select guidance shouldn't
    # leak in when the user already made the choice
    assert "Pick assets whose tags best match" not in fake_llm.last_prompt


def test_email_agent_hides_assets_when_imagery_is_text_only(sample_campaign_brief, sample_context, sample_assets):
    text_only_brief = EmailBrief(imagery=EmailImagery.TEXT_ONLY)
    fake_llm = FakeLLMClient(
        {"subject_lines": ["Hi", "Hello"], "html_body": "<p>hi</p>", "referenced_asset_ids": []}
    )
    agent = EmailContentAgent(fake_llm)

    agent.generate(
        campaign_brief=sample_campaign_brief,
        email_brief=text_only_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert "asset-clubhouse-1" not in fake_llm.last_prompt


def test_email_agent_generates_more_subject_lines_without_touching_rest_of_draft(
    sample_campaign_brief, sample_context
):
    fake_llm = FakeLLMClient({"subject_lines": ["A fresh angle 🏡", "Another new hook ✨", "Third option 🔑"]})
    agent = EmailContentAgent(fake_llm)

    existing = ["Your riverside 3BHK awaits", "Book a site visit this week"]
    more = agent.generate_more_subject_lines(
        campaign_brief=sample_campaign_brief, context=sample_context, existing_subject_lines=existing
    )

    assert more == ["A fresh angle 🏡", "Another new hook ✨", "Third option 🔑"]
    # the existing lines must be shown to the model so it doesn't repeat them
    assert "Your riverside 3BHK awaits" in fake_llm.last_prompt
    assert "P51700012345" in fake_llm.last_prompt


def test_whatsapp_agent_selects_image_when_required(
    sample_campaign_brief, sample_whatsapp_brief, sample_context, sample_assets
):
    fake_llm = FakeLLMClient(
        {
            "message_variants": [
                "Riverside 3BHKs at Skyline Heights, Bandra East. Visit this weekend! 🏡",
                "Your dream 3BHK by the river awaits at Skyline Heights ✨",
            ],
            "cta_variants": ["Book a site visit", "Book a site visit"],
            "image_asset_id": "asset-clubhouse-1",
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=sample_whatsapp_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert len(draft.message_variants) == 2
    assert draft.image_asset_id == "asset-clubhouse-1"
    assert "asset-clubhouse-1" in fake_llm.last_prompt
    # the prompt should ask for at least 2 variants, not a single message
    assert "message_variants" in fake_llm.last_prompt
    # the prompt should push for a line-broken, partly-bold message, not a
    # single flowing paragraph -- this is what backs the WhatsApp-style
    # formatting (details as separate lines, key facts in *bold*).
    assert "FORMATTING" in fake_llm.last_prompt
    assert "single asterisks" in fake_llm.last_prompt


def test_whatsapp_agent_forces_selected_asset_id_even_if_llm_picks_differently(
    sample_campaign_brief, sample_context, sample_assets
):
    whatsapp_brief = WhatsAppBrief(cta_required=True, image_required=True, selected_asset_id="asset-3bhk-1")
    # LLM ignores the instruction and picks the other candidate -- the agent
    # must still force it back to the user's explicit pick.
    fake_llm = FakeLLMClient(
        {
            "message_variants": ["Riverside 3BHKs at Skyline Heights.", "Book your visit today."],
            "cta_variants": ["Book a site visit", "Book a site visit"],
            "image_asset_id": "asset-clubhouse-1",
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=whatsapp_brief,
        context=sample_context,
        candidate_assets=[a for a in sample_assets if a.asset_id == "asset-3bhk-1"],
    )

    assert draft.image_asset_id == "asset-3bhk-1"
    assert "explicitly picked" in fake_llm.last_prompt
    assert "asset-3bhk-1" in fake_llm.last_prompt


def test_whatsapp_agent_skips_asset_selection_when_image_not_required(
    sample_campaign_brief, sample_context, sample_assets
):
    whatsapp_brief = WhatsAppBrief(cta_required=True, image_required=False)
    # LLM misbehaves and returns an id anyway -- the agent must still null it out.
    fake_llm = FakeLLMClient(
        {
            "message_variants": ["Riverside 3BHKs at Skyline Heights."],
            "cta_variants": ["Book a site visit"],
            "image_asset_id": "asset-clubhouse-1",
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=whatsapp_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert draft.image_asset_id is None
    # candidate assets should never have been shown to the model at all
    assert "asset-clubhouse-1" not in fake_llm.last_prompt


def test_whatsapp_agent_nulls_cta_when_not_required(sample_campaign_brief, sample_context, sample_assets):
    whatsapp_brief = WhatsAppBrief(cta_required=False, image_required=False)
    # LLM misbehaves and returns cta_variants anyway -- the agent must still null it out.
    fake_llm = FakeLLMClient(
        {
            "message_variants": ["Riverside 3BHKs at Skyline Heights."],
            "cta_variants": ["Book now"],
            "image_asset_id": None,
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=whatsapp_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert draft.cta_variants is None


def test_whatsapp_agent_assigns_one_cta_per_variant_when_two_options_given(
    sample_campaign_brief, sample_context, sample_assets
):
    whatsapp_brief = WhatsAppBrief(cta_required=True, image_required=False, secondary_cta_text="Call now")
    fake_llm = FakeLLMClient(
        {
            "message_variants": ["Variant one copy.", "Variant two copy.", "Variant three copy."],
            "cta_variants": ["Book a site visit", "Call now", "Book a site visit"],
            "image_asset_id": None,
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=whatsapp_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert draft.cta_variants == ["Book a site visit", "Call now", "Book a site visit"]
    # both CTA options should reach the prompt so the model can assign them
    assert "Book a site visit" in fake_llm.last_prompt
    assert "Call now" in fake_llm.last_prompt


def test_whatsapp_agent_rebuilds_cta_variants_when_llm_returns_wrong_length(
    sample_campaign_brief, sample_context, sample_assets
):
    whatsapp_brief = WhatsAppBrief(cta_required=True, image_required=False, secondary_cta_text="Call now")
    # LLM only returns 1 cta_variant despite 2 message_variants -- the agent
    # must rebuild the list itself rather than trust the model's count.
    fake_llm = FakeLLMClient(
        {
            "message_variants": ["Variant one copy.", "Variant two copy."],
            "cta_variants": ["Book a site visit"],
            "image_asset_id": None,
        }
    )
    agent = WhatsAppContentAgent(fake_llm)

    draft = agent.generate(
        campaign_brief=sample_campaign_brief,
        whatsapp_brief=whatsapp_brief,
        context=sample_context,
        candidate_assets=sample_assets,
    )

    assert draft.cta_variants == ["Book a site visit", "Call now"]
