"""Guidelines service — stores and serves per-project BP chunks and KO guides."""
from __future__ import annotations

import json
from pathlib import Path

from publicaition.services.base import GuidelinesService, LLMService

DEFAULT_STORE_DIR = Path.home() / ".publicaition" / "guidelines"

EXTRACTION_SYSTEM_PROMPT = """You are a medical writing assistant. Extract section-specific guidance from the provided document.

For each of the following section types, extract the relevant guidance as a focused, concise chunk of text:
methods, results, discussion, introduction, conclusion, abstract, pls

Return JSON with section_type keys and extracted guidance as string values.
If the document contains no guidance for a section, return an empty string for that key."""


class PublicAItionGuidelinesService(GuidelinesService):
    """
    File-based guidelines store. One JSON file per project.
    Extraction runs once at project setup via extract_and_store().
    """

    def __init__(self, llm: LLMService, store_dir: Path = DEFAULT_STORE_DIR) -> None:
        self._llm = llm
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    async def get_bp(self, project_id: str, section_type: str) -> str:
        data = self._load(project_id)
        return data.get("bp_chunks", {}).get(section_type, "")

    async def get_ko_guide(self, project_id: str, section_type: str) -> str:
        data = self._load(project_id)
        return data.get("ko_guides", {}).get(section_type, "")

    async def store_extraction(
        self,
        project_id: str,
        bp_chunks: dict[str, str],
        ko_guides: dict[str, str],
    ) -> None:
        self._save(project_id, {"bp_chunks": bp_chunks, "ko_guides": ko_guides})

    async def extract_and_store(
        self,
        project_id: str,
        guidelines_text: str,
        ko_transcript_text: str,
    ) -> None:
        """
        Run extraction against guidelines doc and KO transcript.
        Called once at project setup. Results stored for all pipeline runs.
        """
        bp_chunks, ko_guides = await self._extract_both(guidelines_text, ko_transcript_text)
        await self.store_extraction(project_id, bp_chunks, ko_guides)

    async def _extract_both(
        self,
        guidelines_text: str,
        ko_text: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        bp_user = f"BEST PRACTICE GUIDELINES DOCUMENT:\n\n{guidelines_text}"
        ko_user = f"KICKOFF CALL TRANSCRIPT OR NOTES:\n\n{ko_text}"

        import asyncio
        bp_raw, ko_raw = await asyncio.gather(
            self._llm.generate_json(EXTRACTION_SYSTEM_PROMPT, bp_user),
            self._llm.generate_json(EXTRACTION_SYSTEM_PROMPT, ko_user),
        )

        section_types = ["methods", "results", "discussion", "introduction", "conclusion", "abstract", "pls"]
        bp_chunks = {s: bp_raw.get(s, "") for s in section_types}
        ko_guides = {s: ko_raw.get(s, "") for s in section_types}

        return bp_chunks, ko_guides

    def _path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def _load(self, project_id: str) -> dict:
        path = self._path(project_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _save(self, project_id: str, data: dict) -> None:
        self._path(project_id).write_text(json.dumps(data, indent=2))
