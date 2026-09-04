from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class Purpose(str, Enum):
    PRODUCT_ANNOUNCEMENT = "product_announcement"
    NEWSLETTER = "newsletter"
    PROMO_SALE = "promo_sale"
    EVENT_INVITE = "event_invite"
    WELCOME_ONBOARDING = "welcome_onboarding"
    TRANSACTIONAL_RECEIPT = "transactional_receipt"
    FOLLOW_UP_NUDGE = "follow_up_nudge"
    PAYMENT_POSSESSION_REMINDER = "payment_possession_reminder"
    OTHER = "other"


class AudienceTone(str, Enum):
    CONSUMERS_CASUAL = "consumers_casual"
    CONSUMERS_PREMIUM = "consumers_premium"
    B2B_PROFESSIONAL = "b2b_professional"
    INTERNAL_TEAM = "internal_team"
    COMMUNITY_NEWSLETTER = "community_newsletter"


class CampaignBrief(BaseModel):
    """Shared across every channel in a campaign. Asked once regardless of
    how many channels are selected, since these describe the campaign
    itself (what it's for, what it says, who it's to) rather than any one
    channel's rendering of it.
    """

    purpose: Purpose
    purpose_other_description: Optional[str] = None
    key_message: str
    cta_text: str
    audience_tone: AudienceTone

    @model_validator(mode="after")
    def _require_description_when_other(self) -> "CampaignBrief":
        if self.purpose == Purpose.OTHER and not (self.purpose_other_description or "").strip():
            raise ValueError("purpose_other_description is required when purpose is 'other'")
        return self


class EmailLength(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class EmailImagery(str, Enum):
    TEXT_ONLY = "text_only"
    PLACEHOLDER_BLOCKS = "placeholder_blocks"
    USE_ASSET_BANK = "use_asset_bank"


class EmailBrief(BaseModel):
    """Email-unique fields only -- anything shared with WhatsApp (key
    message, CTA text, audience/tone) lives on CampaignBrief instead.
    """

    design_system_id: Optional[str] = None
    length: EmailLength = EmailLength.MEDIUM
    imagery: EmailImagery = EmailImagery.USE_ASSET_BANK
    # User-picked asset_ids, in order (first = hero/main image, rest = smaller
    # supporting images) -- only meaningful when imagery is USE_ASSET_BANK.
    # Empty means "let the agent choose from CANDIDATE ASSETS" (current
    # tag-matching behavior), same as not picking anything today.
    selected_asset_ids: list[str] = Field(default_factory=list, max_length=4)


class WhatsAppLength(str, Enum):
    SHORT = "short"
    STANDARD = "standard"


class WhatsAppBrief(BaseModel):
    cta_required: bool = True
    image_required: bool = False
    length: WhatsAppLength = WhatsAppLength.STANDARD
    # Optional 2nd CTA option (alongside CampaignBrief.cta_text) -- when set,
    # the two are A/B tested across message_variants, one CTA per variant,
    # instead of every variant sharing a single CTA.
    secondary_cta_text: Optional[str] = None
    # A user-picked image overrides the AI's auto-pick, same idea as
    # EmailBrief.selected_asset_ids -- singular here because WhatsAppDraft
    # only ever carries one image_asset_id.
    selected_asset_id: Optional[str] = None


class CampaignRequest(BaseModel):
    """The Orchestrator's entry point. Which channels run is implied by
    which channel briefs are present -- there's no separate `channels`
    list, since a scenario where e.g. `email_brief` is set but email
    shouldn't run doesn't make sense.
    """

    project_id: str
    campaign_id: str
    campaign_brief: CampaignBrief
    email_brief: Optional[EmailBrief] = None
    whatsapp_brief: Optional[WhatsAppBrief] = None

    @model_validator(mode="after")
    def _require_at_least_one_channel(self) -> "CampaignRequest":
        if self.email_brief is None and self.whatsapp_brief is None:
            raise ValueError("At least one of email_brief or whatsapp_brief must be provided")
        return self

    @property
    def channels(self) -> list[Channel]:
        result = []
        if self.email_brief is not None:
            result.append(Channel.EMAIL)
        if self.whatsapp_brief is not None:
            result.append(Channel.WHATSAPP)
        return result
