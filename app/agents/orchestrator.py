import operator
from typing import Annotated, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, START, StateGraph

from app.agents.asset_agent import AssetAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.context_agent import ContextAgent
from app.agents.email_agent import EmailContentAgent
from app.agents.library_agent import ContentLibraryAgent
from app.agents.whatsapp_agent import WhatsAppContentAgent
from app.models import (
    Asset,
    AssetQuery,
    CampaignBrief,
    CampaignRequest,
    Channel,
    ComplianceIssue,
    EmailBrief,
    EmailDraft,
    ProjectContext,
    WhatsAppBrief,
    WhatsAppDraft,
)


def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


class OrchestratorState(TypedDict):
    request: CampaignRequest
    context: Optional[ProjectContext]
    candidate_assets: List[Asset]
    email_draft: Optional[EmailDraft]
    whatsapp_draft: Optional[WhatsAppDraft]
    email_approved: Optional[bool]
    whatsapp_approved: Optional[bool]
    # Both channel branches can write these in the same run, so they need a
    # merge reducer -- plain TypedDict fields default to "last write wins",
    # which would silently drop one channel's creative_id/status note.
    creative_ids: Annotated[Dict[str, str], _merge_dicts]
    status_notes: Annotated[List[str], operator.add]


class OrchestratorResult(TypedDict):
    creative_ids: Dict[str, str]
    status_notes: List[str]


class DraftReview(TypedDict):
    draft: Union[EmailDraft, WhatsAppDraft]
    approved: bool
    issues: List[ComplianceIssue]


class Orchestrator:
    """Fans out to the Context and Asset agents in parallel, fans back into
    whichever content agents the request actually asked for (implied by
    which of email_brief/whatsapp_brief is present, not a separate channel
    list), routes each draft through Compliance/QA, and only hands approved
    drafts to the Library agent. A rejected draft shows up as a status note
    carrying the blocking issue codes, not a creative ID -- callers can tell
    "channel was skipped" apart from "channel failed compliance" by reading
    the notes.
    """

    def __init__(
        self,
        context_agent: ContextAgent,
        asset_agent: AssetAgent,
        email_agent: EmailContentAgent,
        whatsapp_agent: WhatsAppContentAgent,
        compliance_agent: ComplianceAgent,
        library_agent: ContentLibraryAgent,
    ):
        self._context_agent = context_agent
        self._asset_agent = asset_agent
        self._email_agent = email_agent
        self._whatsapp_agent = whatsapp_agent
        self._compliance_agent = compliance_agent
        self._library_agent = library_agent
        self._graph = self._build_graph()

    def run(self, request: CampaignRequest) -> OrchestratorResult:
        # request.channels being non-empty is already enforced by
        # CampaignRequest's own validator at parse time.
        initial_state: OrchestratorState = {
            "request": request,
            "context": None,
            "candidate_assets": [],
            "email_draft": None,
            "whatsapp_draft": None,
            "email_approved": None,
            "whatsapp_approved": None,
            "creative_ids": {},
            "status_notes": [],
        }
        final_state = self._graph.invoke(initial_state)
        return {"creative_ids": final_state["creative_ids"], "status_notes": final_state["status_notes"]}

    def generate_drafts(self, request: CampaignRequest) -> Dict[str, DraftReview]:
        """Generates and compliance-checks drafts for every requested
        channel but does NOT save anything -- this is the "review before
        you save" step. Saving is a separate, explicit call
        (ContentLibraryAgent.save), so nothing lands in the library until
        the caller says so.
        """
        context = self._context_agent.get_context(
            project_id=request.project_id, query_text=request.campaign_brief.key_message
        )

        result: Dict[str, DraftReview] = {}
        if request.email_brief is not None:
            draft = self._email_agent.generate(
                campaign_brief=request.campaign_brief,
                email_brief=request.email_brief,
                context=context,
                candidate_assets=self._email_candidate_assets(
                    request.project_id, request.campaign_brief, request.email_brief
                ),
            )
            result["email"] = self._review(draft, Channel.EMAIL, context)
        if request.whatsapp_brief is not None:
            draft = self._whatsapp_agent.generate(
                campaign_brief=request.campaign_brief,
                whatsapp_brief=request.whatsapp_brief,
                context=context,
                candidate_assets=self._whatsapp_candidate_assets(
                    request.project_id, request.campaign_brief, request.whatsapp_brief
                ),
            )
            result["whatsapp"] = self._review(draft, Channel.WHATSAPP, context)
        return result

    def _email_candidate_assets(self, project_id: str, campaign_brief: CampaignBrief, email_brief: EmailBrief):
        # A user-picked image list takes priority over tag-matching -- fetch
        # exactly those assets, in the order picked, so the agent can't
        # substitute a different one. Falls back to the usual semantic
        # search when nothing was explicitly picked.
        if email_brief.selected_asset_ids:
            return self._asset_agent.get_by_ids(project_id, email_brief.selected_asset_ids)
        return self._asset_agent.search(
            AssetQuery(project_id=project_id, semantic_query=campaign_brief.key_message, limit=5)
        )

    def _whatsapp_candidate_assets(
        self, project_id: str, campaign_brief: CampaignBrief, whatsapp_brief: WhatsAppBrief
    ):
        # Same override-over-search idea as _email_candidate_assets, just for
        # a single asset_id instead of a list.
        if whatsapp_brief.selected_asset_id:
            return self._asset_agent.get_by_ids(project_id, [whatsapp_brief.selected_asset_id])
        return self._asset_agent.search(
            AssetQuery(project_id=project_id, semantic_query=campaign_brief.key_message, limit=5)
        )

    def revise_email(
        self,
        *,
        project_id: str,
        campaign_brief: CampaignBrief,
        email_brief: EmailBrief,
        current_draft: EmailDraft,
        instruction: str,
    ) -> DraftReview:
        context = self._context_agent.get_context(project_id=project_id, query_text=campaign_brief.key_message)
        candidate_assets = self._email_candidate_assets(project_id, campaign_brief, email_brief)
        draft = self._email_agent.revise(
            campaign_brief=campaign_brief,
            email_brief=email_brief,
            context=context,
            current_draft=current_draft,
            instruction=instruction,
            candidate_assets=candidate_assets,
        )
        return self._review(draft, Channel.EMAIL, context)

    def generate_more_subject_lines(
        self, *, project_id: str, campaign_brief: CampaignBrief, existing_subject_lines: List[str]
    ) -> List[str]:
        context = self._context_agent.get_context(project_id=project_id, query_text=campaign_brief.key_message)
        return self._email_agent.generate_more_subject_lines(
            campaign_brief=campaign_brief, context=context, existing_subject_lines=existing_subject_lines
        )

    def revise_whatsapp(
        self,
        *,
        project_id: str,
        campaign_brief: CampaignBrief,
        whatsapp_brief: WhatsAppBrief,
        current_draft: WhatsAppDraft,
        instruction: str,
    ) -> DraftReview:
        context = self._context_agent.get_context(project_id=project_id, query_text=campaign_brief.key_message)
        candidate_assets = self._whatsapp_candidate_assets(project_id, campaign_brief, whatsapp_brief)
        draft = self._whatsapp_agent.revise(
            campaign_brief=campaign_brief,
            whatsapp_brief=whatsapp_brief,
            context=context,
            current_draft=current_draft,
            instruction=instruction,
            candidate_assets=candidate_assets,
        )
        return self._review(draft, Channel.WHATSAPP, context)

    def _review(self, draft, channel: Channel, context: ProjectContext) -> DraftReview:
        result = self._compliance_agent.review(draft=draft, channel=channel, facts=context.facts)
        return {
            "draft": result.corrected_draft if result.corrected_draft is not None else draft,
            "approved": result.approved,
            "issues": result.issues,
        }

    def _build_graph(self):
        graph = StateGraph(OrchestratorState)

        graph.add_node("context", self._run_context)
        graph.add_node("assets", self._run_assets)
        graph.add_node("join", lambda state: {})
        graph.add_node("email_content", self._run_email_content)
        graph.add_node("email_compliance", self._run_email_compliance)
        graph.add_node("email_library", self._run_email_library)
        graph.add_node("whatsapp_content", self._run_whatsapp_content)
        graph.add_node("whatsapp_compliance", self._run_whatsapp_compliance)
        graph.add_node("whatsapp_library", self._run_whatsapp_library)

        graph.add_edge(START, "context")
        graph.add_edge(START, "assets")
        graph.add_edge("context", "join")
        graph.add_edge("assets", "join")

        graph.add_conditional_edges("join", self._route_channels, ["email_content", "whatsapp_content"])

        graph.add_edge("email_content", "email_compliance")
        graph.add_edge("email_compliance", "email_library")
        graph.add_edge("email_library", END)

        graph.add_edge("whatsapp_content", "whatsapp_compliance")
        graph.add_edge("whatsapp_compliance", "whatsapp_library")
        graph.add_edge("whatsapp_library", END)

        return graph.compile()

    @staticmethod
    def _route_channels(state: OrchestratorState) -> List[str]:
        request = state["request"]
        next_nodes = []
        if request.email_brief is not None:
            next_nodes.append("email_content")
        if request.whatsapp_brief is not None:
            next_nodes.append("whatsapp_content")
        return next_nodes

    def _run_context(self, state: OrchestratorState) -> dict:
        request = state["request"]
        context = self._context_agent.get_context(
            project_id=request.project_id, query_text=request.campaign_brief.key_message
        )
        return {"context": context}

    def _run_assets(self, state: OrchestratorState) -> dict:
        request = state["request"]
        assets = self._asset_agent.search(
            AssetQuery(project_id=request.project_id, semantic_query=request.campaign_brief.key_message, limit=5)
        )
        return {"candidate_assets": assets}

    def _run_email_content(self, state: OrchestratorState) -> dict:
        request = state["request"]
        draft = self._email_agent.generate(
            campaign_brief=request.campaign_brief,
            email_brief=request.email_brief,
            context=state["context"],
            candidate_assets=state["candidate_assets"],
        )
        return {"email_draft": draft}

    def _run_email_compliance(self, state: OrchestratorState) -> dict:
        result = self._compliance_agent.review(
            draft=state["email_draft"], channel=Channel.EMAIL, facts=state["context"].facts
        )
        update: dict = {"status_notes": [self._format_note("email", result)], "email_approved": result.approved}
        if result.corrected_draft is not None:
            update["email_draft"] = result.corrected_draft
        return update

    def _run_email_library(self, state: OrchestratorState) -> dict:
        if not state["email_approved"]:
            return {}
        request, draft = state["request"], state["email_draft"]
        creative_id = self._library_agent.save(
            project_id=request.project_id,
            campaign_id=request.campaign_id,
            channel=Channel.EMAIL,
            variant_label="primary",
            content=draft,
            asset_ids=draft.referenced_asset_ids,
        )
        return {"creative_ids": {"email": creative_id}, "status_notes": [f"email: saved as {creative_id}"]}

    def _run_whatsapp_content(self, state: OrchestratorState) -> dict:
        request = state["request"]
        draft = self._whatsapp_agent.generate(
            campaign_brief=request.campaign_brief,
            whatsapp_brief=request.whatsapp_brief,
            context=state["context"],
            candidate_assets=state["candidate_assets"],
        )
        return {"whatsapp_draft": draft}

    def _run_whatsapp_compliance(self, state: OrchestratorState) -> dict:
        result = self._compliance_agent.review(
            draft=state["whatsapp_draft"], channel=Channel.WHATSAPP, facts=state["context"].facts
        )
        update: dict = {
            "status_notes": [self._format_note("whatsapp", result)],
            "whatsapp_approved": result.approved,
        }
        if result.corrected_draft is not None:
            update["whatsapp_draft"] = result.corrected_draft
        return update

    def _run_whatsapp_library(self, state: OrchestratorState) -> dict:
        if not state["whatsapp_approved"]:
            return {}
        request, draft = state["request"], state["whatsapp_draft"]
        asset_ids = [draft.image_asset_id] if draft.image_asset_id else []
        creative_id = self._library_agent.save(
            project_id=request.project_id,
            campaign_id=request.campaign_id,
            channel=Channel.WHATSAPP,
            variant_label="primary",
            content=draft,
            asset_ids=asset_ids,
        )
        return {"creative_ids": {"whatsapp": creative_id}, "status_notes": [f"whatsapp: saved as {creative_id}"]}

    @staticmethod
    def _format_note(channel: str, result) -> str:
        note = f"{channel}: {'approved' if result.approved else 'REJECTED'}"
        if result.issues:
            note += " - " + "; ".join(f"{i.severity.value}:{i.code}" for i in result.issues)
        return note
