"""Citations skill — validates every claim and inserts citation markers."""
from __future__ import annotations

from publicaition.orchestrator.state import Draft
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate
from publicaition.skills.base import AbstractSkill

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


class CitationsSkill(AbstractSkill):
    """
    Validates claims in all completed drafts and inserts citation markers.
    Unlike other skills, CitationsSkill operates on the full assembled draft,
    not a single section. Library retrieval is done per-claim.
    """
    section_type = "citations"
    retrieves = False   # retrieval is done claim-by-claim inside run()

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
    ) -> tuple[str, str]:
        # Not used directly — run() is overridden
        return SYSTEM_PROMPT, ""

    async def run(self, top_k: int = 8) -> Draft:  # type: ignore[override]
        """
        Annotate all assembled draft sections with citation markers.
        Sections are passed via brief.key_points[0] as a serialized draft
        (set by the runner before calling build_skill for citations).
        """
        # The runner passes the assembled draft text via brief
        full_draft = "\n\n".join(self.brief.key_points) if self.brief.key_points else ""
        if not full_draft:
            return Draft(section_type="citations", text="", metadata={"error": "No draft text provided."})

        # Retrieve supporting evidence for the full draft
        chunks = await self._retrieve(top_k)
        evidence = _format_evidence(chunks)

        user = f"""Annotate the manuscript draft below with citation markers.

LIBRARY EVIDENCE:
{evidence}

MANUSCRIPT DRAFT:
{full_draft}

Apply markers per the legend. Return annotated draft + reference list + unresolved markers."""

        response = await self.services.llm.generate(SYSTEM_PROMPT, user, max_tokens=8192)
        return Draft(
            section_type="citations",
            text=response.text,
            metadata={"input_tokens": response.input_tokens, "output_tokens": response.output_tokens},
        )

    def _enrich_query(self) -> str:
        return f"{self.context.indication} {self.context.primary_endpoint} clinical trial results"


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No library evidence retrieved."
    return "\n\n".join(
        f"[chunk:{c.chunk_id}] {c.source_filename} (p.{c.page_num or '?'}, score={c.score:.2f}):\n{c.text}"
        for c in chunks
    )
