from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class EmailDraft(BaseModel):
    subject_lines: list[str] = Field(..., min_length=1, description="2-3 A/B variants")
    html_body: str
    referenced_asset_ids: list[str] = Field(default_factory=list)


class WhatsAppDraft(BaseModel):
    # Multiple full message variants, same idea as EmailDraft.subject_lines --
    # image_asset_id is shared across all variants, only the message copy
    # and CTA vary per variant.
    message_variants: list[str] = Field(..., min_length=1, description="2+ variants for A/B testing")
    # Parallel to message_variants (same length) when WhatsAppBrief.cta_required
    # is True -- lets up to 2 user-picked CTA options be A/B tested alongside
    # the message copy itself, one CTA per variant. None when cta_required is
    # False -- not every WhatsApp message needs an explicit call to action.
    cta_variants: Optional[list[str]] = None
    image_asset_id: Optional[str] = None


class IssueSeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


class ComplianceIssue(BaseModel):
    code: str = Field(..., description="e.g. 'missing_rera_disclaimer', 'guaranteed_language'")
    message: str
    severity: IssueSeverity


class ComplianceResult(BaseModel):
    """Auto-fixable issues (e.g. an omitted disclaimer line) get folded into
    `corrected_draft` and `approved` stays true; blocking issues (e.g. a
    fabricated possession date) leave `approved=False` for a human to look
    at rather than being silently patched.
    """

    approved: bool
    issues: list[ComplianceIssue] = Field(default_factory=list)
    corrected_draft: Optional[Union[EmailDraft, WhatsAppDraft]] = None
