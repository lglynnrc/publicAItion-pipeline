"""Revision quality evaluation service."""
from __future__ import annotations

from publicaition.services.base import EvaluationResult, EvaluationService, LLMService

SYSTEM_PROMPT = """You are a medical writing quality evaluator. Score a revised manuscript section across six dimensions.

Return JSON with:
- overall: float 0.0–5.0 (mean of dimensions)
- dimensions: object with keys: citation_density, word_limit, journal_style, accuracy_preservation, unverified_claims, outline_adherence — each float 0.0–5.0
- feedback: string, 2–4 sentences of specific, actionable feedback

Scoring guidelines:
- citation_density: Are factual claims supported by citations?
- word_limit: Does the section respect the journal's word count target?
- journal_style: Does tone, structure, and voice match the target journal?
- accuracy_preservation: Are the core scientific claims from the original preserved?
- unverified_claims: Are there claims without evidence? (5 = none, 0 = many)
- outline_adherence: Does the section follow the brief's key points?"""


class PublicAItionEvaluationService(EvaluationService):
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def evaluate(
        self,
        original: str,
        revised: str,
        section_type: str,
        journal: str,
    ) -> EvaluationResult:
        user = f"""SECTION TYPE: {section_type}
TARGET JOURNAL: {journal}

ORIGINAL:
{original}

REVISED:
{revised}

Score the revised section. Return JSON."""

        result = await self._llm.generate_json(SYSTEM_PROMPT, user)
        dimensions = result.get("dimensions", {})
        overall = result.get("overall", sum(dimensions.values()) / len(dimensions) if dimensions else 0.0)

        return EvaluationResult(
            overall=round(float(overall), 2),
            dimensions={k: round(float(v), 2) for k, v in dimensions.items()},
            feedback=result.get("feedback", ""),
        )
