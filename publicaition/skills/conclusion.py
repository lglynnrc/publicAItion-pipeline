"""Conclusion skill — lean, data-anchored, no new claims."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


class ConclusionSkill(MultiSectionSkill):
    section_type = "conclusion"
    retrieves = False   # Methods + Results only — no source materials, no literature

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Conclusion section of a primary research article.

ROLE: Distill the study's key finding into a restrained, data-anchored conclusion. No new claims. No data not already in Methods or Results. No speculation. No recommendations beyond what the data directly supports.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "One to three sentences. State the primary finding and its direct implication. Restrained language. No overreach."}

KICKOFF GUIDANCE:
{self.ko_guide or "Match the benefit-risk framing agreed at kickoff."}

JOURNAL REQUIREMENTS:
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: ~{template.max_words} words
- No data from literature — Methods and Results only
- No figures or table references
- No new claims introduced here for the first time
- Past tense for findings, present tense for implications if appropriate"""

        methods_text = upstream_drafts.get("methods", Draft("methods", "")).text
        results_text = upstream_drafts.get("results", Draft("results", "")).text
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else "- Summarize the primary finding"
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Conclusion section.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Primary endpoint: {self.context.primary_endpoint}

KEY POINTS:
{key_points}{direction}

FINALIZED METHODS:
{methods_text}

FINALIZED RESULTS:
{results_text}

Write the Conclusion. ~{template.max_words} words. No new claims. No literature. Restrained."""

        return system, user
