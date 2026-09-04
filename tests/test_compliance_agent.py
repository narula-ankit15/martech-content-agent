from app.agents.compliance_agent import ComplianceAgent
from app.models import EmailDraft, ProjectFacts, WhatsAppDraft
from app.models.brief import Channel


def _facts_factory(sample_context):
    return sample_context.facts


def test_missing_rera_disclaimer_is_auto_fixed_not_blocking(sample_context):
    facts = _facts_factory(sample_context)
    draft = EmailDraft(subject_lines=["Hi"], html_body="<p>Come visit Skyline Heights</p>")
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.EMAIL, facts=facts)

    assert result.approved is True
    assert any(i.code == "missing_rera_disclaimer" for i in result.issues)
    assert facts.rera_number in result.corrected_draft.html_body


def test_guaranteed_language_blocks_approval(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(
        message_variants=[f"Guaranteed returns at Skyline Heights! RERA: {facts.rera_number}"], cta_variants=["Book now"]
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is False
    assert any(i.code == "guaranteed_language" for i in result.issues)


def test_possession_date_mismatch_blocks_approval(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(
        message_variants=[f"Move in by 2025! RERA: {facts.rera_number}"], cta_variants=["Book now"]
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is False
    assert any(i.code == "possession_date_mismatch" for i in result.issues)


def test_unresolved_personalization_token_blocks_approval(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(
        message_variants=[f"Hi {{{{unknown_token}}}}, visit us! RERA: {facts.rera_number}"], cta_variants=["Book now"]
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is False
    assert any(i.code == "unresolved_personalization_token" for i in result.issues)


def test_invalid_html_blocks_approval(sample_context):
    facts = _facts_factory(sample_context)
    draft = EmailDraft(
        subject_lines=["Hi"], html_body=f"<p>Visit Skyline Heights <strong>now</p> RERA: {facts.rera_number}"
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.EMAIL, facts=facts)

    assert result.approved is False
    assert any(i.code == "invalid_html" for i in result.issues)


def test_char_limit_exceeded_blocks_approval(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(message_variants=["Visit us! " * 50 + f"RERA: {facts.rera_number}"], cta_variants=["Book now"])
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is False
    assert any(i.code == "char_limit_exceeded" for i in result.issues)


def test_char_limit_check_flags_only_the_offending_variant(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(
        message_variants=[f"Visit us! RERA: {facts.rera_number}", "Visit us! " * 50 + f"RERA: {facts.rera_number}"],
        cta_variants=["Book now", "Book now"],
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is False
    issues = [i for i in result.issues if i.code == "char_limit_exceeded"]
    assert len(issues) == 1
    assert "Variant 2" in issues[0].message


def test_clean_draft_is_approved_with_no_issues(sample_context):
    facts = _facts_factory(sample_context)
    draft = WhatsAppDraft(
        message_variants=[
            f"Riverside 3BHKs from {list(facts.price_bands.values())[0]} at Skyline Heights. RERA: {facts.rera_number}"
        ],
        cta_variants=["Book a site visit"],
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.WHATSAPP, facts=facts)

    assert result.approved is True
    assert result.issues == []
    assert result.corrected_draft is None


def test_self_closed_br_tag_is_not_flagged_as_invalid_html(sample_context):
    facts = _facts_factory(sample_context)
    draft = EmailDraft(
        subject_lines=["Hi"],
        html_body=f"<p>Visit Skyline Heights<br/>RERA: {facts.rera_number}</p>",
    )
    agent = ComplianceAgent()

    result = agent.review(draft=draft, channel=Channel.EMAIL, facts=facts)

    assert result.approved is True
    assert not any(i.code == "invalid_html" for i in result.issues)


def test_price_check_recognizes_plural_lakhs_not_just_singular():
    facts = ProjectFacts(
        project_name="Crown Greens",
        rera_number="PR123",
        price_bands={"2BHK": "Starting Rs 87 Lakhs* (carpet area 718-824 sq.ft)"},
    )
    agent = ComplianceAgent()

    matching_draft = WhatsAppDraft(message_variants=["2BHK homes starting Rs 87 Lakhs. RERA: PR123"], cta_variants=["Visit"])
    matching_result = agent.review(draft=matching_draft, channel=Channel.WHATSAPP, facts=facts)
    assert not any(i.code == "unverified_price_claim" for i in matching_result.issues)

    fabricated_draft = WhatsAppDraft(message_variants=["2BHK homes starting Rs 50 Lakhs. RERA: PR123"], cta_variants=["Visit"])
    fabricated_result = agent.review(draft=fabricated_draft, channel=Channel.WHATSAPP, facts=facts)
    assert any(i.code == "unverified_price_claim" for i in fabricated_result.issues)
