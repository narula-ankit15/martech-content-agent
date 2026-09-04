import json
from typing import Optional

from app.agents.llm_client import LLMClient
from app.agents.prompt_helpers import campaign_context_block
from app.models import Asset, CampaignBrief, EmailBrief, EmailDraft, EmailImagery, EmailLength, ProjectContext

SYSTEM_PROMPT = """You are a real-estate marketing designer/copywriter generating a polished, on-brand marketing
email (HTML) for a CRM campaign -- the kind of email that should make the reader stop scrolling, not a plain
text-in-a-box message.
Rules:
- Use ONLY the facts given in PROJECT FACTS and RELEVANT BROCHURE EXCERPTS. Never invent prices, dates, RERA numbers, or unit configs.
- Match the requested audience/tone.
- Use the CTA TEXT verbatim as the label of the primary call-to-action button.
- Follow the IMAGERY instruction exactly. If told to use the asset bank, reference asset_ids from CANDIDATE ASSETS -- never invent one, and never invent a real-looking image URL (see IMAGERY for the exact src format to use). Otherwise don't reference any asset_id.
- Follow the LAYOUT guidance below to build a genuinely good-looking, multi-block email, not a single paragraph.
- Use a tasteful emoji in most subject_lines where it fits the tone naturally (e.g. real-estate-relevant: 🏡 🔑 📍 ✨ 🎉) -- skip emojis entirely for a b2b_professional or internal_team audience.
- Return strictly the JSON schema described in the prompt, nothing else.
"""

LAYOUT_GUIDANCE = """LAYOUT: Build the email as a sequence of distinct visual blocks/sections, like a modern real-estate
landing page compressed into an email -- not one undifferentiated block of text. Aim for 5-8 sections, for example:
  1. HERO -- a full-width banner image (if imagery allows) with the headline and a short supporting line beneath it.
  2. INTRO -- 1-2 sentences on the key message, in a comfortable reading size.
  3. HIGHLIGHTS/AMENITIES -- 2-3 short feature callouts laid out side by side (as table cells), each its own small
     colored panel with a bold label and one line of detail (e.g. "📍 Location", "🏊 Amenities", "🏗️ Possession").
     These do NOT need images -- a tinted background color and clean typography is the point.
  4. PRICING -- a standalone callout panel in a distinct accent background color with the starting price stated
     boldly, using PROJECT FACTS only.
  5. A secondary lifestyle/interior image block (if more than one candidate asset fits and imagery allows), with a
     short caption -- vary this from the hero so the email doesn't feel repetitive.
  6. CTA -- the primary button, centered, in its own section with breathing room around it.
  7. FOOTER -- small, muted text for the RERA disclaimer and a one-line unsubscribe/legal note.
Vary section background colors (alternate white/near-white with 1-2 tasteful accent tints drawn from a cohesive
real-estate-appropriate palette -- warm neutrals, deep green, terracotta, or a palette implied by DESIGN SYSTEM if
given) so the email has visual rhythm instead of looking flat. Use generous padding, rounded corners on image and
panel blocks, and a clear typographic hierarchy (large bold headline, medium section headers, readable body text).
HTML must be email-client-safe: build the layout with <table> elements (not CSS grid/flexbox), inline `style="..."`
attributes only (no <style> blocks, no external stylesheets/fonts, no <script>), and keep the whole email within a
600px-wide canvas. Every section must render correctly even without images, since not all blocks carry one."""

RESPONSE_SCHEMA_HINT = """Respond with JSON matching exactly:
{
  "subject_lines": ["...", "...", "..."],
  "html_body": "...",
  "referenced_asset_ids": ["..."]
}
subject_lines must have 2-3 variants for A/B testing, each meaningfully different (not minor rewording), most
using a tasteful emoji per the system rules. referenced_asset_ids should only include asset_ids actually used in
html_body, or be an empty list.
"""

MORE_SUBJECT_LINES_SYSTEM_PROMPT = """You generate additional email subject line options for a real-estate marketing campaign.
Rules:
- Use ONLY the facts given in PROJECT FACTS and RELEVANT BROCHURE EXCERPTS. Never invent prices, dates, RERA numbers, or unit configs.
- Match the requested audience/tone.
- Generate subject lines that take a meaningfully different angle from both each other and from EXISTING SUBJECT
  LINES -- new hooks/emphasis, not minor rewording of what's already there.
- Use a tasteful emoji in most subject lines where it fits the tone naturally (e.g. real-estate-relevant: 🏡 🔑 📍 ✨ 🎉) -- skip emojis entirely for a b2b_professional or internal_team audience.
- Return strictly the JSON schema described in the prompt, nothing else.
"""

MORE_SUBJECT_LINES_RESPONSE_SCHEMA_HINT = """Respond with JSON matching exactly:
{
  "subject_lines": ["...", "...", "..."]
}
Generate exactly 3 new subject lines. Do not repeat or lightly reword any line from EXISTING SUBJECT LINES.
"""

REVISE_SYSTEM_PROMPT = """You are revising a previously generated marketing email based on the user's feedback.
Rules:
- Use ONLY the facts given in PROJECT FACTS and RELEVANT BROCHURE EXCERPTS. Never invent prices, dates, RERA numbers, or unit configs.
- Apply the user's requested change described in USER'S REQUESTED CHANGE to CURRENT DRAFT. Keep everything else
  about the draft as close to the original as makes sense, unless the instruction implies a broader rewrite.
- Still follow the original CTA TEXT, LENGTH, and IMAGERY guidance below unless the instruction explicitly asks
  to change one of those.
- Still follow the LAYOUT guidance below -- a revision should stay a polished multi-block email, not collapse into
  a plain paragraph, unless the instruction explicitly asks for that.
- Still use a tasteful emoji in most subject_lines (skip for b2b_professional/internal_team) unless the
  instruction explicitly asks to change that.
- Return strictly the JSON schema described in the prompt, nothing else.
"""

_LENGTH_GUIDANCE = {
    EmailLength.SHORT: (
        "Keep copy tight throughout (short intro, 2 highlight callouts, brief pricing line), but still build the "
        "full block structure from LAYOUT -- short means concise copy per section, not fewer sections."
    ),
    EmailLength.MEDIUM: (
        "Give each section in LAYOUT a normal amount of copy: a 2-3 sentence intro, 3 highlight callouts, and a "
        "proper pricing/CTA section."
    ),
    EmailLength.LONG: (
        "Go deeper in each section: a fuller intro, 3-4 highlight callouts, more amenity/USP detail, and use a "
        "second image block if assets allow, while still following the same overall block structure."
    ),
}

_IMAGERY_GUIDANCE = {
    EmailImagery.TEXT_ONLY: (
        "Do not reference any image or asset_id anywhere. Build every block from LAYOUT using only text and "
        "colored panel backgrounds -- no image tags at all."
    ),
    EmailImagery.PLACEHOLDER_BLOCKS: (
        'Do not reference a real asset_id. Wherever LAYOUT calls for an image (hero, and a secondary image block '
        'for medium/long emails), insert a styled placeholder block instead of an <img>, e.g. '
        '<div style="background:#eee;border-radius:12px;padding:60px 20px;text-align:center;color:#888;">'
        '[IMAGE PLACEHOLDER]</div> -- keep its size and position consistent with where a real image would sit.'
    ),
    EmailImagery.USE_ASSET_BANK: (
        "Reference a hero asset_id from CANDIDATE ASSETS for the top banner, and -- for medium/long emails, if a "
        "second visually distinct asset fits (different tags than the hero) -- a second asset_id for the "
        "secondary image block in LAYOUT. Pick assets whose tags best match the content of that section. "
        'You do not know the real image URLs, so set every such <img> src to the literal placeholder '
        '"asset://{asset_id}" (e.g. src="asset://crown-greens-img-pool-01") -- the platform resolves '
        "this to the real URL later. Never invent a real-looking URL or domain, and never reuse the same "
        "asset_id for two different blocks."
    ),
}


def _selected_assets_imagery_line(selected_asset_ids: list[str]) -> str:
    # The user picked these specific images themselves (not the agent) --
    # CANDIDATE ASSETS has been narrowed to exactly this list, in this
    # order, so "pick the best-matching asset" guidance doesn't apply here.
    count = len(selected_asset_ids)
    gallery_line = (
        f"The remaining {count - 1} asset_id(s), in the given order, are smaller supporting images -- place them "
        "below the hero in a compact gallery/highlights row (side-by-side table cells, each noticeably smaller "
        "than the hero), not as a single full-width secondary image block.\n"
        if count > 1
        else ""
    )
    return (
        f"The user explicitly picked {count} image(s) for this email -- CANDIDATE ASSETS lists exactly these, in "
        "this order. You MUST use every one of them and MUST NOT select or invent any other asset_id:\n"
        "  - The FIRST asset_id is the HERO/main image -- large, at the top, in LAYOUT's HERO section.\n"
        f"{gallery_line}"
        'You do not know the real image URLs, so set every such <img> src to the literal placeholder '
        '"asset://{asset_id}" -- the platform resolves this to the real URL later. Never invent a real-looking '
        "URL or domain."
    )


class EmailContentAgent:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def generate(
        self,
        *,
        campaign_brief: CampaignBrief,
        email_brief: EmailBrief,
        context: ProjectContext,
        candidate_assets: Optional[list[Asset]] = None,
    ) -> EmailDraft:
        # Only show real assets when the brief actually asks for the asset
        # bank -- text_only/placeholder_blocks shouldn't tempt the model
        # into inventing or misusing an asset_id.
        assets = (candidate_assets or []) if email_brief.imagery == EmailImagery.USE_ASSET_BANK else []
        prompt = self._build_prompt(campaign_brief, email_brief, context, assets)
        raw = self._llm.generate_json(system=SYSTEM_PROMPT, prompt=prompt)
        return EmailDraft.model_validate(raw)

    def revise(
        self,
        *,
        campaign_brief: CampaignBrief,
        email_brief: EmailBrief,
        context: ProjectContext,
        current_draft: EmailDraft,
        instruction: str,
        candidate_assets: Optional[list[Asset]] = None,
    ) -> EmailDraft:
        assets = (candidate_assets or []) if email_brief.imagery == EmailImagery.USE_ASSET_BANK else []
        base_prompt = self._build_prompt(campaign_brief, email_brief, context, assets)
        prompt = (
            f"CURRENT DRAFT: {current_draft.model_dump_json()}\n\n"
            f"USER'S REQUESTED CHANGE: {instruction}\n\n"
            f"{base_prompt}"
        )
        raw = self._llm.generate_json(system=REVISE_SYSTEM_PROMPT, prompt=prompt)
        return EmailDraft.model_validate(raw)

    def generate_more_subject_lines(
        self,
        *,
        campaign_brief: CampaignBrief,
        context: ProjectContext,
        existing_subject_lines: list[str],
    ) -> list[str]:
        """Generates additional subject line options without touching the
        rest of the draft -- backs the "generate more options" action in the
        subject line picker, which shouldn't have to regenerate the whole
        email just to get a couple more headlines to choose from.
        """
        facts = context.facts.model_dump(exclude_none=True)
        chunks = [c.text for c in context.retrieved_chunks]
        prompt = (
            f"{campaign_context_block(campaign_brief)}"
            f"EXISTING SUBJECT LINES: {json.dumps(existing_subject_lines)}\n\n"
            f"PROJECT FACTS: {json.dumps(facts)}\n\n"
            f"RELEVANT BROCHURE EXCERPTS: {json.dumps(chunks)}\n\n"
            f"{MORE_SUBJECT_LINES_RESPONSE_SCHEMA_HINT}"
        )
        raw = self._llm.generate_json(system=MORE_SUBJECT_LINES_SYSTEM_PROMPT, prompt=prompt)
        return list(raw.get("subject_lines") or [])

    def _build_prompt(
        self,
        campaign_brief: CampaignBrief,
        email_brief: EmailBrief,
        context: ProjectContext,
        candidate_assets: list[Asset],
    ) -> str:
        facts = context.facts.model_dump(exclude_none=True)
        chunks = [c.text for c in context.retrieved_chunks]
        assets = [{"asset_id": a.asset_id, "tags": a.tags} for a in candidate_assets]
        design_note = f"DESIGN SYSTEM: {email_brief.design_system_id}\n" if email_brief.design_system_id else ""
        if email_brief.imagery == EmailImagery.USE_ASSET_BANK and email_brief.selected_asset_ids:
            imagery_line = _selected_assets_imagery_line(email_brief.selected_asset_ids)
        else:
            imagery_line = _IMAGERY_GUIDANCE[email_brief.imagery]
        return (
            f"{campaign_context_block(campaign_brief)}"
            f"CTA TEXT (use verbatim as the primary button label): {campaign_brief.cta_text}\n"
            f"LENGTH: {_LENGTH_GUIDANCE[email_brief.length]}\n"
            f"IMAGERY: {imagery_line}\n"
            f"{design_note}\n"
            f"{LAYOUT_GUIDANCE}\n\n"
            f"PROJECT FACTS: {json.dumps(facts)}\n\n"
            f"RELEVANT BROCHURE EXCERPTS: {json.dumps(chunks)}\n\n"
            f"CANDIDATE ASSETS: {json.dumps(assets)}\n\n"
            f"{RESPONSE_SCHEMA_HINT}"
        )
