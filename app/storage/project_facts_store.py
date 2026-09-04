import json
from pathlib import Path

from app.models import ProjectFacts, ProjectSummary


class ProjectFactsStore:
    """Structured facts (RERA number, pricing, possession date, ...) live
    as one JSON file per project rather than going through retrieval --
    these are the numbers a content agent must reproduce exactly, so they
    come from a source of truth, not a similarity search.
    """

    def __init__(self, base_path: str):
        self._base_path = Path(base_path)

    def get(self, project_id: str) -> ProjectFacts:
        facts_path = self._base_path / project_id / "facts.json"
        if not facts_path.exists():
            raise FileNotFoundError(f"No structured facts found for project '{project_id}' at {facts_path}")
        return ProjectFacts.model_validate(json.loads(facts_path.read_text()))

    def list_projects(self) -> list[ProjectSummary]:
        # A project only counts as usable once it has a facts.json -- a bare
        # directory (e.g. one scaffolded but never filled in) shouldn't show
        # up as a pickable project.
        if not self._base_path.is_dir():
            return []
        summaries = []
        for entry in sorted(self._base_path.iterdir()):
            facts_path = entry / "facts.json"
            if not facts_path.exists():
                continue
            facts = ProjectFacts.model_validate(json.loads(facts_path.read_text()))
            summaries.append(ProjectSummary(project_id=entry.name, project_name=facts.project_name))
        return summaries
