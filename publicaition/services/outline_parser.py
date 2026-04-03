"""Outline parser — normalises a structured DOCX outline into the section brief schema."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from docx import Document
from docx.text.paragraph import Paragraph

from publicaition.services.base import LLMService

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Section type detection — regex first, Claude fallback
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: dict[str, re.Pattern] = {
    "abstract":     re.compile(r"\babstract\b", re.IGNORECASE),
    "introduction": re.compile(r"\b(introduction|background)\b", re.IGNORECASE),
    "methods":      re.compile(r"\b(methods?|patients?\s+and\s+methods?|materials?\s+and\s+methods?|study\s+design)\b", re.IGNORECASE),
    "results":      re.compile(r"\b(results?|findings?|outcomes?)\b", re.IGNORECASE),
    "discussion":   re.compile(r"\bdiscussion\b", re.IGNORECASE),
    "conclusion":   re.compile(r"\b(conclusion[s]?|summary)\b", re.IGNORECASE),
}

_CLASSIFIER_SYSTEM = """You are a medical manuscript analyst. Given a list of section headings from a manuscript outline, classify each heading as one of:
methods, results, discussion, introduction, conclusion, abstract, unknown

Return JSON:
{
  "classifications": {
    "<heading text>": "<section_type>"
  }
}

Use "unknown" only if the heading genuinely cannot be mapped to a standard manuscript section."""


@dataclass
class OutlineSection:
    """One section extracted from a DOCX outline."""
    section_type: str
    label: str
    key_points: list[str] = field(default_factory=list)
    direction_note: str = ""


class OutlineParserService:
    """
    Parses a structured DOCX outline into a list of OutlineSections.

    Detection strategy:
    1. Extract headings and body text from the DOCX.
    2. Try regex against each heading to identify section_type.
    3. For any unmatched headings, call Claude in a single batch to classify them.
    4. Extract key points from the body paragraphs under each heading.
    """

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def parse_docx(self, file_path: str | Path) -> list[OutlineSection]:
        """
        Parse a DOCX outline file and return a list of OutlineSections.
        Raises FileNotFoundError if the path does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Outline file not found: {path}")

        doc = Document(str(path))
        raw_sections = _extract_raw_sections(doc)

        # Resolve section types — regex first, then LLM batch for unknowns
        unmatched = [s for s in raw_sections if not _detect_section_type(s["heading"])]
        if unmatched:
            classifications = await self._classify_headings([s["heading"] for s in unmatched])
        else:
            classifications = {}

        result: list[OutlineSection] = []
        for raw in raw_sections:
            section_type = _detect_section_type(raw["heading"]) or classifications.get(raw["heading"], "unknown")
            result.append(OutlineSection(
                section_type=section_type,
                label=raw["heading"],
                key_points=raw["key_points"],
                direction_note=raw["direction_note"],
            ))

        return result

    async def _classify_headings(self, headings: list[str]) -> dict[str, str]:
        """Batch-classify headings that regex could not resolve."""
        heading_list = "\n".join(f"- {h}" for h in headings)
        user = f"""Classify the following manuscript outline headings:\n\n{heading_list}"""
        result = await self._llm.generate_json(_CLASSIFIER_SYSTEM, user, max_tokens=1024)
        return result.get("classifications", {})


# ---------------------------------------------------------------------------
# DOCX extraction helpers
# ---------------------------------------------------------------------------

def _is_heading(para: Paragraph) -> bool:
    return para.style.name.startswith("Heading")


def _extract_raw_sections(doc: Document) -> list[dict]:
    """
    Walk document paragraphs and group body text under the preceding heading.
    Returns a list of dicts: {heading, key_points, direction_note}.
    """
    sections: list[dict] = []
    current: dict | None = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if _is_heading(para):
            if current is not None:
                sections.append(current)
            current = {"heading": text, "key_points": [], "direction_note": ""}
        elif current is not None:
            # Heuristic: a paragraph starting with "Direction:" or "Note:" becomes direction_note
            lower = text.lower()
            if lower.startswith("direction:") or lower.startswith("note:"):
                current["direction_note"] = re.sub(r"^(direction|note):\s*", "", text, flags=re.IGNORECASE).strip()
            else:
                current["key_points"].append(text)

    if current is not None:
        sections.append(current)

    return sections


def _detect_section_type(heading: str) -> str | None:
    """Return the section_type if the heading matches a known pattern, else None."""
    for section_type, pattern in _SECTION_PATTERNS.items():
        if pattern.search(heading):
            return section_type
    return None
