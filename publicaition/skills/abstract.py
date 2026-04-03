"""Abstract skill — structured compression of all five sections."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


class AbstractSkill(MultiSectionSkill):
    section_type = "abstract"
    retrieves = False   # reads all 5 finalized sections — no retrieval needed

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting the Abstract of a primary research article.

ROLE: Compress the full manuscript into a structured summary. Every number must match the Results section exactly — no rounding, no paraphrasing of statistics. All key data including confidence intervals and p-values must appear.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Structured abstract: Background, Methods, Results, Conclusions. All key efficacy and safety data with CIs. Match Results exactly."}

KICKOFF GUIDANCE:
{self.ko_guide or "Match Results exactly. Include NCT number."}

JOURNAL REQUIREMENTS ({template.citation_style} citations):
{template.drafting_instructions or "Follow journal style."}

STRUCTURAL REQUIREMENTS:
- Word count: {template.max_words} words
- Structured format with labeled subsections
- Every statistic must be verbatim from the Results section
- No citations in the abstract
- No information not present in the manuscript sections provided"""

        sections = {
            "methods":      upstream_drafts.get("methods",      Draft("methods",      "")).text,
            "results":      upstream_drafts.get("results",      Draft("results",      "")).text,
            "discussion":   upstream_drafts.get("discussion",   Draft("discussion",   "")).text,
            "introduction": upstream_drafts.get("introduction", Draft("introduction", "")).text,
            "conclusion":   upstream_drafts.get("conclusion",   Draft("conclusion",   "")).text,
        }
        key_points = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else ""
        direction = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Draft the Abstract for this manuscript.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Phase: {self.context.study_phase}
- Primary endpoint: {self.context.primary_endpoint}
- Journal: {self.context.journal}

{"KEY POINTS:" + chr(10) + key_points if key_points else ""}{direction}

INTRODUCTION:
{sections["introduction"]}

METHODS:
{sections["methods"]}

RESULTS:
{sections["results"]}

DISCUSSION:
{sections["discussion"]}

CONCLUSION:
{sections["conclusion"]}

Write the structured Abstract. {template.max_words} words. Every number must match Results exactly."""

        return system, user
