"""Pipeline runner — reads the DAG, calls skills, manages state."""
from __future__ import annotations

import asyncio

from publicaition.orchestrator.dag import DAG, DAGNode, load_dag
from publicaition.orchestrator.review import PipelinePaused, gate_for
from publicaition.orchestrator.state import Draft, PipelineState, PipelineStatus, ProjectInputs
from publicaition.skills.registry import build_skill
from publicaition.services.container import Services


async def run(
    manuscript_type: str,
    inputs: ProjectInputs,
    services: Services,
    state: PipelineState | None = None,
    section_type: str | None = None,    # required for single_node mode
) -> PipelineState:
    dag = load_dag(manuscript_type)
    state = state or PipelineState(inputs.context.project_id, manuscript_type)
    state.status = PipelineStatus.RUNNING

    try:
        if dag.execution_mode == "single_node":
            assert section_type, "section_type required for single_node mode"
            await _execute_node(dag.nodes[section_type], dag, inputs, services, state)
        else:
            for stage in dag.topological_stages():
                await asyncio.gather(*[
                    _execute_node(dag.nodes[s], dag, inputs, services, state)
                    for s in stage if s not in state.completed
                ])
    except PipelinePaused:
        return state
    except Exception:
        state.status = PipelineStatus.ERROR
        raise

    state.status = PipelineStatus.COMPLETE
    return state


async def _execute_node(
    node: DAGNode,
    dag: DAG,
    inputs: ProjectInputs,
    services: Services,
    state: PipelineState,
) -> None:
    if not node.enabled:
        state.completed.add(node.section_type)
        return

    if node.skill is None:
        await gate_for(node, state).evaluate(node, state)
        state.completed.add(node.section_type)
        return

    upstream = _collect_upstream(node, state)
    library_ids = _resolve_libraries(node, dag, inputs)
    skill = build_skill(node, inputs, services, library_ids)

    draft = await skill.run(upstream_drafts=upstream) if node.multi_section else await skill.run()
    state.drafts[node.section_type] = draft
    _unpack_cohesion(draft, state)
    state.completed.add(node.section_type)


def _unpack_cohesion(draft: Draft, state: PipelineState) -> None:
    """
    Cohesion returns four outputs inside Draft.metadata["cohesion_outputs"].
    Unpack each into state.drafts so downstream skills (Abstract, PLS) and
    state.draft_for() automatically serve the revised versions.
    """
    outputs = draft.metadata.get("cohesion_outputs")
    if not outputs:
        return
    for key, text in outputs.items():
        if key == "unified_reference_list":
            state.drafts["unified_reference_list"] = Draft(
                section_type="unified_reference_list", text=text
            )
        elif text:
            # e.g. "discussion_revised" → stored under that key
            state.drafts[key] = Draft(section_type=key, text=text)


def _collect_upstream(node: DAGNode, state: PipelineState) -> dict[str, Draft]:
    return {
        s: state.draft_for(s)
        for s in node.upstream_sections
        if isinstance(s, str) and state.draft_for(s) is not None
    }


def _resolve_libraries(node: DAGNode, dag: DAG, inputs: ProjectInputs) -> list[str]:
    """
    Return the library IDs the skill should retrieve from.
    Discussion and Introduction get both source materials and literature.
    Methods and Results get source materials only.
    Conclusion, Abstract, Cohesion, PLS get nothing.
    """
    ids: list[str] = []
    if node.section_type in dag.source_materials_sections():
        if inputs.source_materials_library_id:
            ids.append(inputs.source_materials_library_id)
    if node.section_type in dag.literature_sections():
        if inputs.literature_library_id:
            ids.append(inputs.literature_library_id)
    return ids
