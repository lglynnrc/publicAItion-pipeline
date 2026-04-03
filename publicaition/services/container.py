"""Services container — wires concrete implementations together."""
from __future__ import annotations

from dataclasses import dataclass, field

from publicaition.services.base import (
    EvaluationService,
    FewShotService,
    GuidelinesService,
    HealthGEOService,
    LLMService,
    RetrievalService,
    TemplateService,
)


@dataclass(frozen=True)
class Services:
    retrieval: RetrievalService
    llm: LLMService
    evaluation: EvaluationService
    templates: TemplateService
    few_shot: FewShotService
    guidelines: GuidelinesService
    healthgeo: HealthGEOService | None = field(default=None)  # future state
