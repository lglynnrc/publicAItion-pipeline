"""Pipeline state — inputs going in, drafts and status coming out."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    PAUSED   = "paused"    # waiting at a gate
    COMPLETE = "complete"
    ERROR    = "error"


@dataclass
class SectionBrief:
    """Writer-provided direction for one section."""
    section_type: str
    label: str
    key_points: list[str]
    direction_note: str = ""


@dataclass
class StudyContext:
    """Study-level metadata shared across all skills."""
    project_id: str
    study_name: str
    indication: str
    primary_endpoint: str
    study_phase: str
    comparators: list[str]
    key_takeaways: str        # researcher strategic direction, primary input for Discussion
    author_voice_notes: str
    journal: str


@dataclass
class ProjectInputs:
    """Everything the pipeline needs before the first node runs."""

    # Study identity
    context: StudyContext

    # Qdrant library IDs — None means that library type wasn't provided
    source_materials_library_id: str | None   # CSR, SAP, Tables/Figs
    literature_library_id: str | None          # ~30 reference PDFs

    # Pre-pipeline extractions (stored per project at setup, not re-run)
    bp_chunks: dict[str, str]    # section_type → best-practice chunk text
    ko_guides: dict[str, str]    # section_type → KO call guide text

    # Per-section writer briefs (key_points + direction_note)
    # Populated from the approved outline. Falls back to empty brief if absent.
    section_briefs: dict[str, SectionBrief] = field(default_factory=dict)

    def brief_for(self, section_type: str) -> SectionBrief:
        return self.section_briefs.get(
            section_type,
            SectionBrief(section_type=section_type, label=section_type, key_points=[]),
        )


@dataclass
class Draft:
    """Output of a single skill run."""
    section_type: str
    text: str
    word_count: int = field(init=False)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())


@dataclass
class PipelineState:
    """Mutable state threaded through the runner."""

    project_id: str
    manuscript_type: str

    # Completed drafts — keyed by section_type
    # Cohesion writes revised versions under e.g. "discussion_revised"
    drafts: dict[str, Draft] = field(default_factory=dict)

    # Nodes that have finished (section_type strings)
    completed: set[str] = field(default_factory=set)

    # Nodes that failed — section_type → error message
    failed: dict[str, str] = field(default_factory=dict)

    # Overall pipeline status
    status: PipelineStatus = PipelineStatus.PENDING

    # Set when the pipeline is paused at a gate — identifies which gate
    pending_gate: str | None = None

    # Path selections for dual-path nodes (1A / 1B) — section_type → path_id
    selected_paths: dict[str, str] = field(default_factory=dict)

    def draft_for(self, section_type: str) -> Draft | None:
        """Return revised draft if cohesion ran, otherwise original."""
        revised_key = f"{section_type}_revised"
        return self.drafts.get(revised_key) or self.drafts.get(section_type)
