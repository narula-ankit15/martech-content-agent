import re
from html.parser import HTMLParser
from typing import Union

from app.models import ComplianceIssue, ComplianceResult, EmailDraft, IssueSeverity, ProjectFacts, WhatsAppDraft
from app.models.brief import Channel

GUARANTEED_LANGUAGE_PATTERN = re.compile(r"\b(guarantee|guaranteed|assured returns)\b", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:Crores?|Cr\.?|Lakhs?|L\b)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
KNOWN_PERSONALIZATION_TOKENS = {"first_name", "project_name", "unit_config", "possession_date"}
WHATSAPP_CHAR_LIMIT = 320
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link"}


class _TagBalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        # Self-closed form (<tag/>) is inherently balanced -- HTMLParser's
        # default implementation calls handle_starttag + handle_endtag for
        # this, which would wrongly flag e.g. <br/> as an unmatched close.
        pass

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected closing tag </{tag}>")
        else:
            self.stack.pop()


def _extract_text(draft: Union[EmailDraft, WhatsAppDraft]) -> str:
    if isinstance(draft, EmailDraft):
        return " ".join(draft.subject_lines) + " " + draft.html_body
    return " ".join(draft.message_variants) + " " + " ".join(draft.cta_variants or [])


class ComplianceAgent:
    """Takes the same ProjectFacts the content agents were given, not just
    the draft -- "flag misleading claims" only means something if there's a
    ground truth to check against. Most checks just flag; only the missing
    RERA disclaimer is treated as auto-fixable, since appending a standard
    disclosure line is safe to do mechanically while rewriting marketing
    copy or a fabricated date/price is not.
    """

    def review(self, *, draft: Union[EmailDraft, WhatsAppDraft], channel: Channel, facts: ProjectFacts) -> ComplianceResult:
        working_draft = draft.model_copy(deep=True)
        issues: list[ComplianceIssue] = []

        rera_issues, working_draft = self._check_rera(working_draft, facts, channel)
        issues += rera_issues

        text = _extract_text(working_draft)
        issues += self._check_guaranteed_language(text)
        issues += self._check_price_claims(text, facts)
        issues += self._check_possession_date_claims(text, facts)
        issues += self._check_personalization_tokens(text)

        if channel == Channel.EMAIL:
            issues += self._check_html(working_draft)
        else:
            issues += self._check_char_limit(working_draft)

        blocking = [i for i in issues if i.severity == IssueSeverity.BLOCKING]
        return ComplianceResult(
            approved=len(blocking) == 0,
            issues=issues,
            corrected_draft=working_draft if working_draft != draft else None,
        )

    def _check_rera(self, draft, facts: ProjectFacts, channel: Channel):
        if not facts.rera_number or facts.rera_number in _extract_text(draft):
            return [], draft
        if channel == Channel.EMAIL:
            draft.html_body += (
                f'<p style="font-size:12px;color:#888;">RERA Registration Number: {facts.rera_number}</p>'
            )
        else:
            draft.message_variants = [f"{v} (RERA: {facts.rera_number})" for v in draft.message_variants]
        issue = ComplianceIssue(
            code="missing_rera_disclaimer",
            message=f"RERA number {facts.rera_number} was missing and has been auto-appended",
            severity=IssueSeverity.WARNING,
        )
        return [issue], draft

    def _check_guaranteed_language(self, text: str):
        if GUARANTEED_LANGUAGE_PATTERN.search(text):
            return [
                ComplianceIssue(
                    code="guaranteed_language",
                    message="Content uses prohibited 'guaranteed/assured returns' language",
                    severity=IssueSeverity.BLOCKING,
                )
            ]
        return []

    def _check_price_claims(self, text: str, facts: ProjectFacts):
        known_price_tokens = {
            m.group(0).lower() for value in facts.price_bands.values() for m in PRICE_PATTERN.finditer(value)
        }
        if not known_price_tokens:
            return []
        found = {m.group(0).lower() for m in PRICE_PATTERN.finditer(text)}
        unverified = found - known_price_tokens
        if unverified:
            return [
                ComplianceIssue(
                    code="unverified_price_claim",
                    message=f"Price mention(s) not found in project facts: {sorted(unverified)}",
                    severity=IssueSeverity.WARNING,
                )
            ]
        return []

    def _check_possession_date_claims(self, text: str, facts: ProjectFacts):
        if not facts.possession_date:
            return []
        fact_years = set(YEAR_PATTERN.findall(facts.possession_date))
        draft_years = set(YEAR_PATTERN.findall(text))
        mismatched = draft_years - fact_years
        if mismatched:
            return [
                ComplianceIssue(
                    code="possession_date_mismatch",
                    message=f"Content mentions year(s) {sorted(mismatched)} not matching possession date '{facts.possession_date}'",
                    severity=IssueSeverity.BLOCKING,
                )
            ]
        return []

    def _check_personalization_tokens(self, text: str):
        issues = []
        for match in TOKEN_PATTERN.finditer(text):
            token = match.group(1)
            if token not in KNOWN_PERSONALIZATION_TOKENS:
                issues.append(
                    ComplianceIssue(
                        code="unresolved_personalization_token",
                        message=f"Unknown personalization token: {{{{{token}}}}}",
                        severity=IssueSeverity.BLOCKING,
                    )
                )
        return issues

    def _check_html(self, draft: EmailDraft):
        checker = _TagBalanceChecker()
        checker.feed(draft.html_body)
        if checker.errors or checker.stack:
            detail = "; ".join(checker.errors + [f"unclosed <{t}>" for t in checker.stack])
            return [
                ComplianceIssue(
                    code="invalid_html", message=f"HTML is not well-formed: {detail}", severity=IssueSeverity.BLOCKING
                )
            ]
        return []

    def _check_char_limit(self, draft: WhatsAppDraft):
        issues = []
        for i, variant in enumerate(draft.message_variants):
            cta_text = draft.cta_variants[i] if draft.cta_variants and i < len(draft.cta_variants) else ""
            length = len(variant) + len(cta_text)
            if length > WHATSAPP_CHAR_LIMIT:
                issues.append(
                    ComplianceIssue(
                        code="char_limit_exceeded",
                        message=f"Variant {i + 1} + CTA is {length} chars, over the {WHATSAPP_CHAR_LIMIT} limit",
                        severity=IssueSeverity.BLOCKING,
                    )
                )
        return issues
