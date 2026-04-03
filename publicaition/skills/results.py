"""Results skill — drafts the Results section from source materials + finalized Methods."""
from __future__ import annotations

from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import AbstractSkill


class ResultsSkill(AbstractSkill):
    section_type = "results"

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Results section of a primary research article.

ROLE: Report findings objectively and completely. Results contains no interpretation, no speculation, and no discussion of implications — only accurate reporting of what was observed.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Report all pre-specified outcomes. Include exact statistics with confidence intervals and p-values. Use past tense. No interpretation."}

KICKOFF GUIDANCE:
{self.ko_guide or "Report all outcomes as specified."}

JOURNAL REQUIREMENTS ({template.citation_style} citations):
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: {template.max_words} words
- Use exact subheaders as specified in the journal template
- Every number must come directly from the source data — no rounding without explicit hedging
- Report confidence intervals and p-values for all key outcomes
- Figures and tables should be referenced inline (e.g. "Table 1", "Figure 2")
- Maintain consistency with the Methods section provided

{"EXAMPLES OF ACCEPTED REVISIONS:" + chr(10) + chr(10).join(f"Original: {e.original}{chr(10)}Revised: {e.revised}" for e in examples) if examples else ""}"""

        evidence = _format_chunks(chunks)
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else "- Draft full Results section"
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Results section for this study.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Phase: {self.context.study_phase}
- Primary endpoint: {self.context.primary_endpoint}
- Comparators: {", ".join(self.context.comparators) if self.context.comparators else "N/A"}

KEY POINTS TO COVER:
{key_points}{direction}

SOURCE MATERIAL EXCERPTS (tables, figures, statistical outputs):
{evidence}

Write the complete Results section. {template.max_words} words. Report only — do not interpret."""

        return system, user


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No source material excerpts retrieved."
    return "\n\n".join(
        f"[{i+1}] {c.source_filename} (p.{c.page_num or '?'}, score={c.score:.2f}):\n{c.text}"
        for i, c in enumerate(chunks)
    )
