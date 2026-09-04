from typing import Optional

from pydantic import BaseModel, Field


class ProjectFacts(BaseModel):
    """Structured facts a content agent can drop straight into copy without
    having to parse them out of prose. Kept separate from the retrieved
    chunks below so a content agent can rely on these being exact (e.g. the
    RERA number must never be paraphrased or hallucinated).
    """

    project_name: str
    rera_number: Optional[str] = None
    unit_configs: list[str] = Field(default_factory=list, description="e.g. ['2BHK', '3BHK', '4BHK']")
    price_bands: dict[str, str] = Field(default_factory=dict, description="unit_config -> price range string")
    possession_date: Optional[str] = None
    usps: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)
    location: Optional[str] = None


class ProjectSummary(BaseModel):
    """Lightweight id + display name, for populating a project picker
    without pulling in full ProjectFacts (price bands, USPs, etc.)."""

    project_id: str
    project_name: str


class RetrievedChunk(BaseModel):
    text: str
    source: str = Field(..., description="brochure filename or section this chunk came from")
    score: float


class ProjectContext(BaseModel):
    """Output of the Context agent. Deliberately not a raw brochure dump —
    content agents get exact facts plus a handful of the most relevant
    passages, not the whole document, to keep prompts small and grounded.
    """

    project_id: str
    facts: ProjectFacts
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
