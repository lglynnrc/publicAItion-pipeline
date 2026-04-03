"""Renderer — assembles completed drafts into output documents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from publicaition.orchestrator.state import Draft, PipelineState
from publicaition.outputs.docx import build_docx
from publicaition.outputs.pdf import convert_to_pdf

# Reading order for the final document — distinct from DAG drafting order
DOCUMENT_ORDER = [
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
]


@dataclass
class RenderedOutput:
    docx_path: Path
    pdf_path: Path | None
    word_count: int
    sections_included: list[str]
    missing_sections: list[str]


def render(
    state: PipelineState,
    output_dir: Path,
    project_name: str,
    journal: str,
    include_pls: bool = True,
    include_pdf: bool = True,
) -> RenderedOutput:
    """
    Assemble all finalized drafts into DOCX (and optionally PDF).
    Uses cohesion-revised versions where available via state.draft_for().
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    sections, included, missing = _collect_sections(state)
    reference_list = state.drafts.get("reference_list")
    pls_draft = state.draft_for("pls") if include_pls else None

    docx_path = output_dir / f"{_slug(project_name)}.docx"
    build_docx(
        output_path=docx_path,
        project_name=project_name,
        journal=journal,
        sections=sections,
        reference_list=reference_list,
        pls=pls_draft,
    )

    pdf_path: Path | None = None
    if include_pdf:
        try:
            pdf_path = convert_to_pdf(docx_path)
        except Exception as exc:
            # PDF conversion is best-effort — DOCX is the primary deliverable
            print(f"[renderer] PDF conversion failed: {exc}. DOCX saved at {docx_path}.")

    total_words = sum(s.word_count for s in sections)

    return RenderedOutput(
        docx_path=docx_path,
        pdf_path=pdf_path,
        word_count=total_words,
        sections_included=included,
        missing_sections=missing,
    )


def _collect_sections(state: PipelineState) -> tuple[list[Draft], list[str], list[str]]:
    sections: list[Draft] = []
    included: list[str] = []
    missing: list[str] = []

    for section_type in DOCUMENT_ORDER:
        draft = state.draft_for(section_type)
        if draft and draft.text.strip():
            sections.append(draft)
            included.append(section_type)
        else:
            missing.append(section_type)

    return sections, included, missing


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "-")[:60]
