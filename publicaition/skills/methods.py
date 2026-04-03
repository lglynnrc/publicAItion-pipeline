"""Methods skill — drafts the Methods section from source materials."""
from __future__ import annotations

from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import AbstractSkill


class MethodsSkill(AbstractSkill):
    section_type = "methods"

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Methods section of a primary research article.

ROLE: Translate technical protocol details into a clear, precise narrative. The Methods section should read like a recipe — reproducible, unambiguous, and complete. Follow CONSORT and PICO conventions where applicable.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Apply CONSORT/PICO structure. Write in past tense. Include: study design, population, interventions, outcomes, statistical approach."}

KICKOFF GUIDANCE:
{self.ko_guide or "Follow the study protocol exactly."}

JOURNAL REQUIREMENTS ({template.citation_style} citations):
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: {template.max_words} words
- Use exact subheaders as specified in the journal template
- Past tense throughout
- No interpretation — only design and procedure
- Every procedural detail must be traceable to the source materials

{"EXAMPLES OF ACCEPTED REVISIONS:" + chr(10) + chr(10).join(f"Original: {e.original}{chr(10)}Revised: {e.revised}" for e in examples) if examples else ""}"""

        evidence = _format_chunks(chunks)
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else "- Draft full Methods section"
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Methods section for this study.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Phase: {self.context.study_phase}
- Primary endpoint: {self.context.primary_endpoint}
- Comparators: {", ".join(self.context.comparators) if self.context.comparators else "N/A"}

KEY POINTS TO COVER:
{key_points}{direction}

SOURCE MATERIAL EXCERPTS:
{evidence}

Write the complete Methods section. {template.max_words} words. Do not interpret results."""

        return system, user


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No source material excerpts retrieved."
    return "\n\n".join(
        f"[{i+1}] {c.source_filename} (p.{c.page_num or '?'}, score={c.score:.2f}):\n{c.text}"
        for i, c in enumerate(chunks)
    )
