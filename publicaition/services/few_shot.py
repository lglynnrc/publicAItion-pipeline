"""Few-shot example service — stores and retrieves high-quality revision examples."""
from __future__ import annotations

import json
from pathlib import Path

from publicaition.services.base import FewShotExample, FewShotService

QUALITY_THRESHOLD = 4.0     # minimum score to store an example
DEFAULT_STORE_DIR = Path.home() / ".publicaition" / "few_shot"


class PublicAItionFewShotService(FewShotService):
    """
    File-based few-shot store. One JSON file per project.
    Swap for a database-backed implementation when needed.
    """

    def __init__(self, store_dir: Path = DEFAULT_STORE_DIR) -> None:
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    async def get_examples(
        self,
        project_id: str,
        section_type: str,
        limit: int = 3,
    ) -> list[FewShotExample]:
        examples = self._load(project_id)
        filtered = [e for e in examples if e.section_type == section_type]
        # Most recent high-quality examples first
        filtered.sort(key=lambda e: e.quality_score, reverse=True)
        return filtered[:limit]

    async def store_example(self, project_id: str, example: FewShotExample) -> None:
        if example.quality_score < QUALITY_THRESHOLD:
            return
        examples = self._load(project_id)
        examples.append(example)
        self._save(project_id, examples)

    def _path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def _load(self, project_id: str) -> list[FewShotExample]:
        path = self._path(project_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text())
        return [FewShotExample(**r) for r in raw]

    def _save(self, project_id: str, examples: list[FewShotExample]) -> None:
        raw = [
            {
                "section_type": e.section_type,
                "original": e.original,
                "revised": e.revised,
                "quality_score": e.quality_score,
            }
            for e in examples
        ]
        self._path(project_id).write_text(json.dumps(raw, indent=2))
