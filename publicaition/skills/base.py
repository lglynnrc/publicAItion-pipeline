"""Skill base classes. All section drafting skills extend one of these."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from publicaition.orchestrator.state import Draft, SectionBrief, StudyContext
from publicaition.services.base import FewShotExample, RetrievedChunk, SectionTemplate

if TYPE_CHECKING:
    from publicaition.services.container import Services


class AbstractSkill(ABC):
    """
    Base for skills that draft one section from retrieved evidence.

    Subclasses implement `_build_prompt` and optionally override
    `_enrich_query` to customise retrieval.
    """

    section_type: str   # must be set on each subclass

    def __init__(
        self,
        brief: SectionBrief,
        context: StudyContext,
        services: "Services",           # imported at runtime to avoid circular import
        library_ids: list[str],         # resolved by the runner per DAG context rules
        bp_chunk: str = "",             # section-specific best-practice text
        ko_guide: str = "",             # section-specific KO call guide
    ) -> None:
        self.brief = brief
        self.context = context
        self.services = services
        self.library_ids = library_ids
        self.bp_chunk = bp_chunk
        self.ko_guide = ko_guide

    async def run(self, top_k: int = 12) -> Draft:
        chunks = await self._retrieve(top_k)
        template = self.services.templates.get_section(self.context.journal, self.section_type)
        examples = await self.services.few_shot.get_examples(self.context.project_id, self.section_type)
        system, user = self._build_prompt(chunks, template, examples)
        response = await self.services.llm.generate(system, user)
        return Draft(section_type=self.section_type, text=response.text)

    async def _retrieve(self, top_k: int) -> list[RetrievedChunk]:
        """Retrieve from all assigned libraries and merge by score."""
        if not self.library_ids:
            return []
        results: list[RetrievedChunk] = []
        for lib_id in self.library_ids:
            chunks = await self.services.retrieval.search(
                library_id=lib_id,
                query=self._enrich_query(),
                top_k=top_k,
            )
            results.extend(chunks)
        return sorted(results, key=lambda c: c.score, reverse=True)[:top_k]

    def _enrich_query(self) -> str:
        return f"{self.context.indication} {' '.join(self.brief.key_points)}"

    @abstractmethod
    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt)."""


class MultiSectionSkill(AbstractSkill):
    """
    Base for skills that require completed upstream drafts as input.

    Discussion — reads methods + results + retrieves literature + source materials
    Introduction — reads methods + results + discussion + retrieves both libraries
    Conclusion — reads methods + results, no retrieval
    Abstract — reads all 5 sections, no retrieval
    Cohesion — reads discussion + introduction + conclusion, no retrieval
    PLS — reads full manuscript, no retrieval
    """

    retrieves: bool = True  # set False on subclasses that don't need retrieval

    async def run(                      # type: ignore[override]
        self,
        upstream_drafts: dict[str, Draft],
        top_k: int = 12,
    ) -> Draft:
        chunks = await self._retrieve(top_k) if self.retrieves else []
        template = self.services.templates.get_section(self.context.journal, self.section_type)
        examples = await self.services.few_shot.get_examples(self.context.project_id, self.section_type)
        system, user = self._build_prompt(chunks, template, examples, upstream_drafts)
        response = await self.services.llm.generate(system, user)
        return Draft(section_type=self.section_type, text=response.text)

    @abstractmethod
    def _build_prompt(                  # type: ignore[override]
        self,
        chunks: list[RetrievedChunk],
        template: SectionTemplate,
        examples: list[FewShotExample],
        upstream_drafts: dict[str, Draft],
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) including upstream draft content."""
