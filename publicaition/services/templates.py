"""Journal template service — reads section configs from the existing backend templates."""
from __future__ import annotations

import json
from pathlib import Path

from publicaition.services.base import SectionTemplate, TemplateService

# Templates are loaded from the existing backend config.
# Path is configurable so the new package doesn't hard-code repo layout.
DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent / "config" / "templates"


class PublicAItionTemplateService(TemplateService):
    def __init__(self, template_dir: Path = DEFAULT_TEMPLATE_DIR) -> None:
        self._dir = template_dir
        self._cache: dict[str, dict] = {}

    def get_section(self, journal: str, section_type: str) -> SectionTemplate:
        data = self._load(journal)
        sections = {s["section_type"]: s for s in data.get("sections", [])}

        if section_type not in sections:
            # Return a minimal default rather than raising — skills degrade gracefully
            return SectionTemplate(
                section_type=section_type,
                label=section_type.replace("_", " ").title(),
                max_words=1200,
                drafting_instructions="",
                citation_style=data.get("citation_style", "numbered"),
                presets=[],
            )

        s = sections[section_type]
        return SectionTemplate(
            section_type=section_type,
            label=s.get("label", section_type),
            max_words=s.get("max_words", 1200),
            drafting_instructions=s.get("drafting_instructions", ""),
            citation_style=data.get("citation_style", "numbered"),
            presets=s.get("presets", []),
        )

    def list_journals(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]

    def _load(self, journal: str) -> dict:
        if journal not in self._cache:
            path = self._dir / f"{journal}.json"
            if not path.exists():
                return {}
            with path.open() as f:
                self._cache[journal] = json.load(f)
        return self._cache[journal]
