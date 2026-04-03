"""Discussion skill — interprets Results in light of Methods and published literature."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


class DiscussionSkill(MultiSectionSkill):
    section_type = "discussion"
    retrieves = True    # literature + source materials

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Discussion section of a primary research article.

ROLE: Synthesize the study's results with existing literature to explain the "why" and "so what." Discuss strengths and limitations. Propose mechanisms where evidence supports it. The Introduction (written later) will set up what this Discussion resolves — write to be resolved, not to introduce.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Open with key finding. Place in context of literature. Discuss mechanisms. Address strengths and weaknesses. Avoid overreach."}

KICKOFF GUIDANCE — STRATEGIC PRIORITIES:
{self.ko_guide or "Follow the key takeaways from the research team."}

KEY TAKEAWAYS FROM RESEARCH TEAM:
{self.context.key_takeaways or "Not provided."}

JOURNAL REQUIREMENTS ({template.citation_style} citations):
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: ~{template.max_words} words
- Do not introduce new data not in Methods or Results
- Cross-trial numeric comparisons require explicit sourcing from literature
- Cite published literature for all comparative claims

{"EXAMPLES OF ACCEPTED REVISIONS:" + chr(10) + chr(10).join(f"Original: {e.original}{chr(10)}Revised: {e.revised}" for e in examples) if examples else ""}"""

        methods_text = upstream_drafts.get("methods", Draft("methods", "")).text
        results_text = upstream_drafts.get("results", Draft("results", "")).text
        literature = _format_chunks(chunks)
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else "- Draft full Discussion"
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Discussion section.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Phase: {self.context.study_phase}
- Primary endpoint: {self.context.primary_endpoint}
- Comparators: {", ".join(self.context.comparators) if self.context.comparators else "N/A"}

KEY POINTS TO COVER:
{key_points}{direction}

FINALIZED METHODS SECTION:
{methods_text}

FINALIZED RESULTS SECTION:
{results_text}

LITERATURE EXCERPTS (~{len(chunks)} references):
{literature}

Write the complete Discussion. ~{template.max_words} words."""

        return system, user


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No literature retrieved."
    return "\n\n".join(
        f"[{i+1}] {c.source_filename} (p.{c.page_num or '?'}):\n{c.text}"
        for i, c in enumerate(chunks)
    )
