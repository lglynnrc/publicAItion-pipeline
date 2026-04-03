"""Transcript parser — extracts ProjectInputs and a draft outline from a KO call transcript."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from publicaition.services.base import LLMService

SYSTEM_PROMPT = """You are a medical writing analyst. Given a kick-off (KO) call transcript, extract structured information for a manuscript writing project.

Extract the following and return as JSON:

{
  "study_name": "<study name or trial name>",
  "indication": "<disease/condition being studied>",
  "primary_endpoint": "<primary efficacy endpoint>",
  "study_phase": "<phase I / II / III / IV or other>",
  "comparators": ["<comparator 1>", "<comparator 2>"],
  "key_takeaways": "<strategic direction and key messages from the authors — what this study proves and why it matters>",
  "author_voice_notes": "<author tone preferences, preferred terminology, style notes mentioned in the call>",
  "journal": "<target journal if mentioned, else empty string>",
  "section_key_points": {
    "methods": ["<key point 1>", "<key point 2>"],
    "results": ["<key point 1>", "<key point 2>"],
    "discussion": ["<key point 1>", "<key point 2>"],
    "introduction": ["<key point 1>", "<key point 2>"],
    "conclusion": ["<key point 1>", "<key point 2>"]
  },
  "section_direction_notes": {
    "methods": "<direction note for this section, or empty string>",
    "results": "<direction note for this section, or empty string>",
    "discussion": "<direction note for this section, or empty string>",
    "introduction": "<direction note for this section, or empty string>",
    "conclusion": "<direction note for this section, or empty string>"
  }
}

Rules:
- Extract only what is explicitly stated or clearly implied in the transcript.
- Use empty strings and empty lists for fields not mentioned.
- key_takeaways should capture the authors' strategic intent and the argument they want the manuscript to make.
- section_key_points should be concrete, specific points (data, comparisons, subgroup findings) that should appear in each section."""


@dataclass
class TranscriptExtraction:
    """Structured output from a KO call transcript parse."""
    study_name: str
    indication: str
    primary_endpoint: str
    study_phase: str
    comparators: list[str]
    key_takeaways: str
    author_voice_notes: str
    journal: str
    section_key_points: dict[str, list[str]] = field(default_factory=dict)
    section_direction_notes: dict[str, str] = field(default_factory=dict)


class TranscriptParserService:
    """
    Single-call LLM service that parses a KO call transcript into structured
    ProjectInputs fields and a draft outline. Writer corrects the extraction
    rather than filling forms from scratch.
    """

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def parse(self, transcript_text: str) -> TranscriptExtraction:
        """
        Parse a KO call transcript and return a TranscriptExtraction.
        The caller uses this to pre-fill ProjectInputs and draft SectionBriefs.
        """
        user = f"""Extract the manuscript project information from the following KO call transcript.

TRANSCRIPT:
{transcript_text}

Return the extracted information as JSON per the schema in your instructions."""

        result = await self._llm.generate_json(SYSTEM_PROMPT, user, max_tokens=4096)
        return _build_extraction(result)


def _build_extraction(raw: dict) -> TranscriptExtraction:
    _sections = ["methods", "results", "discussion", "introduction", "conclusion"]
    raw_kp = raw.get("section_key_points") or {}
    raw_dn = raw.get("section_direction_notes") or {}

    return TranscriptExtraction(
        study_name=raw.get("study_name", ""),
        indication=raw.get("indication", ""),
        primary_endpoint=raw.get("primary_endpoint", ""),
        study_phase=raw.get("study_phase", ""),
        comparators=raw.get("comparators") or [],
        key_takeaways=raw.get("key_takeaways", ""),
        author_voice_notes=raw.get("author_voice_notes", ""),
        journal=raw.get("journal", ""),
        section_key_points={s: raw_kp.get(s) or [] for s in _sections},
        section_direction_notes={s: raw_dn.get(s) or "" for s in _sections},
    )
