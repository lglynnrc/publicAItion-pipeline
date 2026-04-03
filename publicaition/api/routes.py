"""Pipeline API routes."""
from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from publicaition.api.models import (
    DraftResponse,
    RunRequest,
    RunResponse,
    RunStateResponse,
    SectionRunRequest,
)
from publicaition.orchestrator import runner
from publicaition.orchestrator.state import (
    PipelineState,
    PipelineStatus,
    ProjectInputs,
    SectionBrief,
    StudyContext,
)
from publicaition.services.container import Services

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _services(request: Request) -> Services:
    return request.app.state.services


def _build_inputs(req: RunRequest | SectionRunRequest) -> ProjectInputs:
    ctx = req.context
    study_context = StudyContext(
        project_id=ctx.project_id,
        study_name=ctx.study_name,
        indication=ctx.indication,
        primary_endpoint=ctx.primary_endpoint,
        study_phase=ctx.study_phase,
        comparators=ctx.comparators,
        key_takeaways=ctx.key_takeaways,
        author_voice_notes=ctx.author_voice_notes,
        journal=ctx.journal,
    )

    section_briefs: dict[str, SectionBrief] = {}

    if isinstance(req, SectionRunRequest):
        if req.brief:
            section_briefs[req.section_type] = SectionBrief(
                section_type=req.brief.section_type,
                label=req.brief.label,
                key_points=req.brief.key_points,
                direction_note=req.brief.direction_note,
            )
    else:
        for stype, brief in req.section_briefs.items():
            section_briefs[stype] = SectionBrief(
                section_type=brief.section_type,
                label=brief.label,
                key_points=brief.key_points,
                direction_note=brief.direction_note,
            )

    return ProjectInputs(
        context=study_context,
        source_materials_library_id=req.source_materials_library_id,
        literature_library_id=req.literature_library_id,
        bp_chunks=req.bp_chunks,
        ko_guides=req.ko_guides,
        section_briefs=section_briefs,
    )


def _serialize_state(run_id: str, state: PipelineState) -> RunStateResponse:
    return RunStateResponse(
        run_id=run_id,
        status=state.status.value,
        manuscript_type=state.manuscript_type,
        completed=sorted(state.completed),
        failed=state.failed,
        drafts={
            key: DraftResponse(
                section_type=draft.section_type,
                text=draft.text,
                word_count=draft.word_count,
                metadata=draft.metadata,
            )
            for key, draft in state.drafts.items()
        },
        pending_gate=state.pending_gate,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=RunResponse, status_code=202)
async def start_run(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    services: Annotated[Services, Depends(_services)],
    request: Request,
) -> RunResponse:
    """
    Start a full pipeline run. Returns immediately with a run_id.
    Poll GET /runs/{run_id} for status and drafts.
    """
    run_id = str(uuid.uuid4())
    inputs = _build_inputs(req)

    state = PipelineState(
        project_id=inputs.context.project_id,
        manuscript_type=req.manuscript_type,
    )
    request.app.state.runs[run_id] = state

    async def _execute() -> None:
        await runner.run(
            manuscript_type=req.manuscript_type,
            inputs=inputs,
            services=services,
            state=state,
        )

    background_tasks.add_task(_execute)

    return RunResponse(
        run_id=run_id,
        status=PipelineStatus.PENDING.value,
        manuscript_type=req.manuscript_type,
    )


@router.get("/runs/{run_id}", response_model=RunStateResponse)
async def get_run(
    run_id: str,
    request: Request,
) -> RunStateResponse:
    """Poll for pipeline state and available drafts."""
    state: PipelineState | None = request.app.state.runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _serialize_state(run_id, state)


@router.post("/section", response_model=DraftResponse)
async def draft_section(
    req: SectionRunRequest,
    services: Annotated[Services, Depends(_services)],
) -> DraftResponse:
    """
    Draft a single section synchronously (section_draft mode).
    Returns the draft when complete. Suitable for iteration loops.
    """
    inputs = _build_inputs(req)
    state = await runner.run(
        manuscript_type="section_draft",
        inputs=inputs,
        services=services,
        section_type=req.section_type,
    )

    draft = state.drafts.get(req.section_type)
    if draft is None:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline completed but no draft found for section '{req.section_type}'",
        )

    return DraftResponse(
        section_type=draft.section_type,
        text=draft.text,
        word_count=draft.word_count,
        metadata=draft.metadata,
    )
