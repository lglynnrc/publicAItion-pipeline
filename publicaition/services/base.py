"""Abstract service interfaces. All concrete implementations depend on these contracts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    source_filename: str
    page_num: int | None
    metadata: dict[str, Any]


class RetrievalService(ABC):
    @abstractmethod
    async def search(
        self,
        library_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Hybrid semantic + keyword search over an ingested library."""


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMService(ABC):
    @abstractmethod
    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Single-turn text generation."""

    @abstractmethod
    async def generate_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> Any:
        """Single-turn generation that returns parsed JSON."""


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationResult:
    overall: float                    # 0.0–5.0
    dimensions: dict[str, float]
    feedback: str


class EvaluationService(ABC):
    @abstractmethod
    async def evaluate(
        self,
        original: str,
        revised: str,
        section_type: str,
        journal: str,
    ) -> EvaluationResult:
        """Score a revision across quality dimensions."""


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SectionTemplate:
    section_type: str
    label: str
    max_words: int
    drafting_instructions: str
    citation_style: str
    presets: list[str]


class TemplateService(ABC):
    @abstractmethod
    def get_section(self, journal: str, section_type: str) -> SectionTemplate:
        """Retrieve journal-specific section configuration."""

    @abstractmethod
    def list_journals(self) -> list[str]:
        """Return available journal identifiers."""


# ---------------------------------------------------------------------------
# Few-shot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FewShotExample:
    section_type: str
    original: str
    revised: str
    quality_score: float


class FewShotService(ABC):
    @abstractmethod
    async def get_examples(
        self,
        project_id: str,
        section_type: str,
        limit: int = 3,
    ) -> list[FewShotExample]:
        """Retrieve high-quality revision examples for a section."""

    @abstractmethod
    async def store_example(
        self,
        project_id: str,
        example: FewShotExample,
    ) -> None:
        """Persist an accepted revision as a future few-shot example."""


# ---------------------------------------------------------------------------
# Guidelines (BP chunks + KO guides — stored per project at setup)
# ---------------------------------------------------------------------------

class GuidelinesService(ABC):
    @abstractmethod
    async def get_bp(self, project_id: str, section_type: str) -> str:
        """Return the best-practice chunk for this section."""

    @abstractmethod
    async def get_ko_guide(self, project_id: str, section_type: str) -> str:
        """Return the KO call guide for this section."""

    @abstractmethod
    async def store_extraction(
        self,
        project_id: str,
        bp_chunks: dict[str, str],
        ko_guides: dict[str, str],
    ) -> None:
        """Persist extracted BP chunks and KO guides for a project."""


# ---------------------------------------------------------------------------
# HealthGEO (future state — term/reference check with live material)
# ---------------------------------------------------------------------------

class HealthGEOService(ABC):
    @abstractmethod
    async def check(self, text: str, section_type: str) -> str:
        """Run HealthGEO optimisation pass. Returns updated text."""
