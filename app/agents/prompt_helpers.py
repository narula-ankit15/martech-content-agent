from app.models import CampaignBrief, Purpose


def humanize(value: str) -> str:
    return value.replace("_", " ").title()


def campaign_context_block(campaign_brief: CampaignBrief) -> str:
    """Fields shared by every channel (purpose, key message, audience/tone).
    CTA text is deliberately excluded here -- each channel agent decides how
    (or whether) to surface `cta_text`, since that's channel-specific.
    """
    purpose_label = humanize(campaign_brief.purpose.value)
    if campaign_brief.purpose == Purpose.OTHER and campaign_brief.purpose_other_description:
        purpose_label = f"{purpose_label} - {campaign_brief.purpose_other_description}"
    return (
        f"CAMPAIGN PURPOSE: {purpose_label}\n"
        f"KEY MESSAGE: {campaign_brief.key_message}\n"
        f"AUDIENCE / TONE: {humanize(campaign_brief.audience_tone.value)}\n"
    )
