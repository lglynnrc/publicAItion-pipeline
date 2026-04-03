"""Citations skill — validates every claim and inserts citation markers."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import MultiSectionSkill

# Marker legend passed to Claude so it applies consistently
MARKER_LEGEND = """Citation marker legend:
[N]   — supported by reference N in the library
[N?]  — reference N exists but the claim overstates or extends the evidence
[?]   — no supporting reference found in the library (reviewer must source or cut)
[!]   — a library reference actively contradicts this claim (reviewer must correct)"""

SYSTEM_PROMPT = f"""You are a medical writing editor performing citation validation on a manuscript draft.

{MARKER_LEGEND}

YOUR TASK:
1. Read the draft section provided.
2. For every factual claim, statistic, or assertion, insert the appropriate marker inline immediately after the claim.
3. Assign [N] markers sequentially starting from 1. Each unique reference gets one number.
4. A single claim may have multiple references: [1,2]
5. Preserve all original wording exactly — only add markers, do not edit prose.
6. Return the annotated text followed by a numbered reference list.

OUTPUT FORMAT:
ANNOTATED DRAFT:
<draft with inline markers>

REFERENCE LIST:
1. <source_filename>, p.<page_num> — <brief excerpt confirming the claim>
2. ...

UNRESOLVED MARKERS:
List all [?] and [!] markers with the claim text and reason."""

# Document section order for draft assembly
_SECTION_ORDER = ["methods", "results", "discussion", "introduction", "conclusion"]


class CitationsSkill(MultiSectionSkill):
    """
    Validates claims across all completed drafts and inserts citation markers.
    Operates on the assembled manuscript (all five sections), not a single section.
    Retrieves from the literature library for reference matching.
    """
    section_type = "citations"
    retrieves = True

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        full_draft = _assemble_draft(upstream_drafts)
        evidence = _format_evidence(chunks)

        user = f"""Annotate the manuscript draft below with citation markers.

LIBRARY EVIDENCE:
{evidence}

MANUSCRIPT DRAFT:
{full_draft}

Apply markers per the legend. Return annotated draft + reference list + unresolved markers."""

        return SYSTEM_PROMPT, user

    async def run(self, upstream_drafts: dict[str, Draft], top_k: int = 8) -> Draft:  # type: ignore[override]
        chunks = await self._retrieve(top_k)
        template = self.services.templates.get_section(self.context.journal, self.section_type)
        examples = await self.services.few_shot.get_examples(self.context.project_id, self.section_type)
        system, user = self._build_prompt(chunks, template, examples, upstream_drafts)
        response = await self.services.llm.generate(system, user, max_tokens=8192)
        return Draft(
            section_type="citations",
            text=response.text,
            metadata={"input_tokens": response.input_tokens, "output_tokens": response.output_tokens},
        )

    def _enrich_query(self) -> str:
        return f"{self.context.indication} {self.context.primary_endpoint} clinical trial results"


def _assemble_draft(upstream_drafts: dict[str, Draft]) -> str:
    sections = []
    for section_type in _SECTION_ORDER:
        draft = upstream_drafts.get(section_type)
        if draft and draft.text:
            sections.append(f"[{section_type.upper()}]\n{draft.text}")
    return "\n\n".join(sections) if sections else ""


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No library evidence retrieved."
    return "\n\n".join(
        f"[chunk:{c.chunk_id}] {c.source_filename} (p.{c.page_num or '?'}, score={c.score:.2f}):\n{c.text}"
        for c in chunks
    )
