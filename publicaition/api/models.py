"""Pydantic request/response models for the pipeline API."""
from __future__ import annotations

from pydantic import BaseModel


class StudyContextPayload(BaseModel):
    project_id: str
    study_name: str
    indication: str
    primary_endpoint: str
    study_phase: str
    comparators: list[str]
    key_takeaways: str
    author_voice_notes: str
    journal: str


class SectionBriefPayload(BaseModel):
    section_type: str
    label: str
    key_points: list[str]
    direction_note: str = ""


class RunRequest(BaseModel):
    manuscript_type: str = "primary_research"
    context: StudyContextPayload
    source_materials_library_id: str | None = None
    literature_library_id: str | None = None
    bp_chunks: dict[str, str] = {}
    ko_guides: dict[str, str] = {}
    section_briefs: dict[str, SectionBriefPayload] = {}


class SectionRunRequest(BaseModel):
    """Single-section draft request (section_draft mode)."""
    section_type: str
    context: StudyContextPayload
    source_materials_library_id: str | None = None
    literature_library_id: str | None = None
    bp_chunks: dict[str, str] = {}
    ko_guides: dict[str, str] = {}
    brief: SectionBriefPayload | None = None


class DraftResponse(BaseModel):
    section_type: str
    text: str
    word_count: int
    metadata: dict = {}


class RunResponse(BaseModel):
    run_id: str
    status: str
    manuscript_type: str


class RunStateResponse(BaseModel):
    run_id: str
    status: str
    manuscript_type: str
    completed: list[str]
    failed: dict[str, str]
    drafts: dict[str, DraftResponse]
    pending_gate: str | None = None
