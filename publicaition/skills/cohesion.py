"""Cohesion skill — surgical alignment of Discussion, Introduction, and Conclusion."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


COHESION_SYSTEM = """You are a medical writing editor performing a cohesion pass on three manuscript sections.

YOUR CONSTRAINTS — READ CAREFULLY:
1. Word counts and section structures must be preserved. This is not a rewrite.
2. Make only surgical edits — the minimum change needed to achieve alignment.
3. Do not add new claims, data, or interpretations not already present.
4. Do not remove content — only rephrase for consistency.

YOUR THREE TASKS:
1. REFERENCE UNIFICATION — merge all in-text citations into a single sequential numbered reference list. Renumber every [N] marker in all three sections to match the unified list. Output the unified reference list as a separate deliverable.
2. NARRATIVE ARC ALIGNMENT — ensure Introduction sets up → Discussion resolves → Conclusion distills. Fix any gaps, contradictions, or misalignments in the argument across sections.
3. WORDING CONSISTENCY — standardize terminology, tone, and parallel construction across all three sections. Flag any term used inconsistently (e.g. "patients" vs "participants", "treatment" vs "therapy").

OUTPUT FORMAT — return JSON with:
{
  "introduction_revised": "<full revised introduction text>",
  "discussion_revised": "<full revised discussion text>",
  "conclusion_revised": "<full revised conclusion text>",
  "unified_reference_list": "<numbered reference list>",
  "changes_summary": "<brief list of edits made>"
}"""


class CohesionSkill(MultiSectionSkill):
    section_type = "cohesion"
    retrieves = False

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        discussion   = upstream_drafts.get("discussion",   Draft("discussion",   "")).text
        introduction = upstream_drafts.get("introduction", Draft("introduction", "")).text
        conclusion   = upstream_drafts.get("conclusion",   Draft("conclusion",   "")).text

        user = f"""Perform the cohesion pass on the three sections below.

JOURNAL: {self.context.journal}
CITATION STYLE: {template.citation_style}

DRAFT DISCUSSION:
{discussion}

DRAFT INTRODUCTION:
{introduction}

DRAFT CONCLUSION:
{conclusion}

Apply all three cohesion tasks. Return the revised sections and unified reference list as JSON."""

        return COHESION_SYSTEM, user

    async def run(self, upstream_drafts: dict[str, Draft], top_k: int = 12) -> Draft:  # type: ignore[override]
        """
        Override run() to handle multi-output.
        Cohesion returns a JSON object — the runner stores each revised section
        under its own key (e.g. "discussion_revised") in PipelineState.drafts.
        """
        template = self.services.templates.get_section(self.context.journal, self.section_type)
        system, user = self._build_prompt([], template, [], upstream_drafts)
        result = await self.services.llm.generate_json(system, user)

        # Store revised sections back onto the state via metadata
        # The runner reads these from Draft.metadata["cohesion_outputs"]
        return Draft(
            section_type="cohesion",
            text=result.get("changes_summary", "Cohesion pass complete."),
            metadata={
                "cohesion_outputs": {
                    "introduction_revised": result.get("introduction_revised", ""),
                    "discussion_revised":   result.get("discussion_revised", ""),
                    "conclusion_revised":   result.get("conclusion_revised", ""),
                    "unified_reference_list": result.get("unified_reference_list", ""),
                }
            },
        )
