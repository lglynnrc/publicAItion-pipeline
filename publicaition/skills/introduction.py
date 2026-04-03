"""Introduction skill — written last, frames what the Discussion resolves."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


class IntroductionSkill(MultiSectionSkill):
    section_type = "introduction"
    retrieves = True    # literature + source materials

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Introduction section of a primary research article.

ROLE: Frame the study precisely. The Introduction is written after the Discussion — it sets up exactly what the Discussion resolves. Structure: background → evidence gap → study rationale → aim. Four paragraphs.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Para 1: disease burden and context. Para 2: current treatments and unmet need. Para 3: evidence gap this study addresses. Para 4: study aim and design overview."}

KICKOFF GUIDANCE:
{self.ko_guide or "Follow the agreed framing from the kickoff call."}

JOURNAL REQUIREMENTS ({template.citation_style} citations):
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: ~{template.max_words} words
- Exactly 4 paragraphs
- Every claim about the literature must be cited
- The final paragraph must state the study aim precisely as described in Methods
- Do not reveal results — Introduction precedes Results in the final manuscript

{"EXAMPLES OF ACCEPTED REVISIONS:" + chr(10) + chr(10).join(f"Original: {e.original}{chr(10)}Revised: {e.revised}" for e in examples) if examples else ""}"""

        methods_text = upstream_drafts.get("methods", Draft("methods", "")).text
        results_text = upstream_drafts.get("results", Draft("results", "")).text
        discussion_text = upstream_drafts.get("discussion", Draft("discussion", "")).text
        literature = _format_chunks(chunks)
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else "- Draft full Introduction"
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Introduction section. Written after Discussion — frame what the Discussion resolves.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Phase: {self.context.study_phase}
- Primary endpoint: {self.context.primary_endpoint}
- Comparators: {", ".join(self.context.comparators) if self.context.comparators else "N/A"}

KEY POINTS TO COVER:
{key_points}{direction}

FINALIZED METHODS (for aim statement accuracy):
{methods_text}

FINALIZED RESULTS (for framing — do not reveal in Introduction):
{results_text[:500]}...

DRAFT DISCUSSION (frame what this resolves):
{discussion_text}

LITERATURE EXCERPTS:
{literature}

Write the Introduction. ~{template.max_words} words. 4 paragraphs. Do not reveal results."""

        return system, user


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No literature retrieved."
    return "\n\n".join(
        f"[{i+1}] {c.source_filename} (p.{c.page_num or '?'}):\n{c.text}"
        for i, c in enumerate(chunks)
    )
