"""
Smoke test — end-to-end wiring check with a real Anthropic API key.

What this verifies:
  runner → registry → skill → services → LLM call → Draft returned

Retrieval is stubbed (no Qdrant required). Everything else is real.

Run with:
    ANTHROPIC_API_KEY=sk-ant-... uv run pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import os

import pytest

from publicaition.orchestrator.runner import run
from publicaition.orchestrator.state import (
    PipelineState,
    PipelineStatus,
    ProjectInputs,
    SectionBrief,
    StudyContext,
)
from publicaition.services.base import (
    EvaluationResult,
    EvaluationService,
    FewShotExample,
    FewShotService,
    GuidelinesService,
    LLMService,
    RetrievedChunk,
    RetrievalService,
)
from publicaition.services.container import Services
from publicaition.services.evaluation import PublicAItionEvaluationService
from publicaition.services.few_shot import PublicAItionFewShotService
from publicaition.services.guidelines import PublicAItionGuidelinesService
from publicaition.services.llm import AnthropicLLMService
from publicaition.services.templates import PublicAItionTemplateService

# Applied per-test to the LLM-calling tests; DAG tests don't need it.
_requires_api_key = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping smoke tests",
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubRetrievalService(RetrievalService):
    """Returns empty results. Smoke test validates wiring, not retrieval quality."""

    async def search(self, library_id: str, query: str, top_k: int) -> list[RetrievedChunk]:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def services() -> Services:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    llm = AnthropicLLMService(api_key=api_key)
    return Services(
        retrieval=StubRetrievalService(),
        llm=llm,
        evaluation=PublicAItionEvaluationService(llm=llm),
        templates=PublicAItionTemplateService(),
        few_shot=PublicAItionFewShotService(),
        guidelines=PublicAItionGuidelinesService(llm=llm),
    )


@pytest.fixture
def minimal_inputs() -> ProjectInputs:
    """Minimal ProjectInputs sufficient for a Methods section draft."""
    return ProjectInputs(
        context=StudyContext(
            project_id="smoke-test-001",
            study_name="PALADIN Study",
            indication="Gastric cancer",
            primary_endpoint="Overall survival at 12 months",
            study_phase="Phase III",
            comparators=["FOLFOX chemotherapy"],
            key_takeaways=(
                "FAc demonstrates superior OS compared to standard chemotherapy "
                "in patients with fast-progressing gastric cancer."
            ),
            author_voice_notes="Third person, conservative hedging, past tense.",
            journal="jama",
        ),
        source_materials_library_id=None,   # no real library needed for smoke test
        literature_library_id=None,
        bp_chunks={},
        ko_guides={},
        section_briefs={
            "methods": SectionBrief(
                section_type="methods",
                label="Methods",
                key_points=[
                    "Randomized, double-blind, placebo-controlled Phase III trial",
                    "Enrolled adults with HER2-negative metastatic gastric adenocarcinoma",
                    "Primary endpoint: overall survival; secondary: PFS, ORR, safety",
                    "Stratified by ECOG performance status and geographic region",
                ],
                direction_note="Lead with study design. Use CONSORT structure.",
            )
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@_requires_api_key
@pytest.mark.asyncio
async def test_section_draft_methods_returns_draft(services: Services, minimal_inputs: ProjectInputs) -> None:
    """
    Run a single Methods section draft in section_draft mode.
    Verifies: runner → registry → MethodsSkill → LLM → Draft returned.
    """
    state = await run(
        manuscript_type="section_draft",
        inputs=minimal_inputs,
        services=services,
        section_type="methods",
    )

    assert isinstance(state, PipelineState)
    assert state.status == PipelineStatus.COMPLETE
    assert "methods" in state.drafts

    draft = state.drafts["methods"]
    assert draft.section_type == "methods"
    assert len(draft.text) > 100, "Draft text should not be empty"
    assert draft.word_count > 0


def test_section_draft_methods_respects_journal_template() -> None:
    """
    Verify the template service resolves JAMA Methods config without raising.
    This catches any mismatch between template files and the TemplateService.
    No API key required.
    """
    templates = PublicAItionTemplateService()
    template = templates.get_section("jama", "methods")
    assert template.section_type == "methods"
    assert template.max_words > 0
    assert template.citation_style == "Vancouver"
    assert "CONSORT" in template.drafting_instructions or "protocol" in template.drafting_instructions.lower()

    # Citations section should resolve without falling back to generic defaults
    citations_template = templates.get_section("jama", "citations")
    assert citations_template.section_type == "citations"


@pytest.mark.asyncio
async def test_dag_loads_and_stages_resolve() -> None:
    """
    Verify all DAGs load cleanly and produce correct stage orders.
    No API key required — this tests config/code wiring only.
    """
    from publicaition.orchestrator.dag import load_dag

    # primary_research
    dag = load_dag("primary_research")
    order = [s for stage in dag.topological_stages() for s in stage]
    assert order.index("methods") < order.index("results")
    assert order.index("results") < order.index("discussion")
    assert order.index("discussion") < order.index("introduction")
    assert order.index("introduction") < order.index("citations")
    assert order.index("citations") < order.index("abstract")
    assert order.index("abstract") < order.index("pls")
    assert order.index("pls") < order.index("review_gate")
    assert order.index("review_gate") < order.index("assembly")

    # section_draft — multi_section flags corrected
    dag_sd = load_dag("section_draft")
    assert dag_sd.execution_mode == "single_node"
    assert dag_sd.nodes["discussion"].multi_section is True
    assert dag_sd.nodes["conclusion"].multi_section is True
    assert dag_sd.nodes["abstract"].multi_section is True
    assert dag_sd.nodes["pls"].multi_section is True

    # poster_abstract
    dag_pa = load_dag("poster_abstract")
    order_pa = [s for stage in dag_pa.topological_stages() for s in stage]
    assert order_pa.index("methods") < order_pa.index("results")
    assert order_pa.index("results") < order_pa.index("conclusion")
    assert order_pa.index("results") < order_pa.index("introduction")
    assert order_pa.index("introduction") < order_pa.index("assembly")
