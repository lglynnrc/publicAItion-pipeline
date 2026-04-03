"""PLS skill — plain language summary for lay audiences."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill


class PLSSkill(MultiSectionSkill):
    section_type = "pls"
    retrieves = False

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        system = f"""You are a medical writer drafting a Plain Language Summary (PLS) for a primary research article.

ROLE: Translate the manuscript into clear, accessible language for patients, caregivers, and non-specialist audiences. Preserve scientific accuracy while removing jargon. Reading level target: US Grade 8–10.

BEST PRACTICE GUIDELINES:
{self.bp_chunk or "Use short sentences. Define medical terms on first use. Lead with 'what this study found'. Explain why it matters to patients."}

KICKOFF GUIDANCE:
{self.ko_guide or "Patient-friendly framing. Emphasize key takeaways."}

JOURNAL PLS REQUIREMENTS:
{template.drafting_instructions or "Follow journal PLS guidelines."}

STRUCTURAL REQUIREMENTS:
- Plain language throughout — no unexplained acronyms or jargon
- Lead with the key finding in one sentence a patient can understand
- Explain what the study did, what was found, and what it means for patients
- Include a "Key Takeaways" bullet list at the end
- Do not introduce claims not in the manuscript"""

        abstract    = upstream_drafts.get("abstract",    Draft("abstract",    "")).text
        conclusion  = upstream_drafts.get("conclusion",  Draft("conclusion",  "")).text
        results     = upstream_drafts.get("results",     Draft("results",     "")).text
        discussion  = upstream_drafts.get("discussion",  Draft("discussion",  "")).text
        key_points  = "\n".join(f"- {p}" for p in self.brief.key_points) if self.brief.key_points else ""
        direction   = f"\nWRITER DIRECTION: {self.brief.direction_note}" if self.brief.direction_note else ""

        user = f"""Write the Plain Language Summary for this manuscript.

STUDY CONTEXT:
- Indication: {self.context.indication}
- Primary endpoint: {self.context.primary_endpoint}

{"KEY POINTS:" + chr(10) + key_points if key_points else ""}{direction}

ABSTRACT:
{abstract}

RESULTS (for accuracy):
{results}

DISCUSSION:
{discussion}

CONCLUSION:
{conclusion}

Write the PLS. Plain language. Grade 8–10 reading level. End with "Key Takeaways" bullets."""

        return system, user
