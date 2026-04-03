"""Qdrant retrieval service — hybrid vector + keyword search."""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from sentence_transformers import SentenceTransformer

from publicaition.services.base import RetrievedChunk, RetrievalService

EMBEDDING_MODEL = "NeuML/pubmedbert-base-embeddings"
RRF_K = 60
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4


@lru_cache(maxsize=1)
def _get_encoder() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def _encode(text: str) -> list[float]:
    return _get_encoder().encode(text, normalize_embeddings=True).tolist()


class QdrantRetrievalService(RetrievalService):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._client = AsyncQdrantClient(url=url, api_key=api_key)

    async def search(
        self,
        library_id: str,
        query: str,
        top_k: int = 12,
    ) -> list[RetrievedChunk]:
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, _encode, query
        )

        vector_hits, keyword_hits = await asyncio.gather(
            self._vector_search(library_id, embedding, top_k),
            self._keyword_search(library_id, query, top_k),
        )

        return _rrf_merge(vector_hits, keyword_hits, top_k)

    async def _vector_search(
        self, library_id: str, embedding: list[float], top_k: int
    ) -> list[ScoredPoint]:
        return await self._client.search(
            collection_name=library_id,
            query_vector=embedding,
            limit=top_k,
            with_payload=True,
        )

    async def _keyword_search(
        self, library_id: str, query: str, top_k: int
    ) -> list[ScoredPoint]:
        """BM25-style keyword search via Qdrant full-text index on the 'text' field."""
        try:
            return await self._client.search(
                collection_name=library_id,
                query_vector=None,  # type: ignore[arg-type]
                query_filter=Filter(
                    must=[FieldCondition(key="text", match=MatchValue(value=query))]
                ),
                limit=top_k,
                with_payload=True,
            )
        except Exception:
            # Full-text index may not be configured — degrade gracefully to vector-only
            return []


def _rrf_merge(
    vector_hits: list[ScoredPoint],
    keyword_hits: list[ScoredPoint],
    top_k: int,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    payloads: dict[str, Any] = {}

    for rank, hit in enumerate(vector_hits):
        key = str(hit.id)
        scores[key] = scores.get(key, 0.0) + VECTOR_WEIGHT / (RRF_K + rank + 1)
        payloads[key] = hit.payload or {}

    for rank, hit in enumerate(keyword_hits):
        key = str(hit.id)
        scores[key] = scores.get(key, 0.0) + KEYWORD_WEIGHT / (RRF_K + rank + 1)
        if key not in payloads:
            payloads[key] = hit.payload or {}

    max_score = max(scores.values()) if scores else 1.0
    sorted_ids = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_k]

    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            text=payloads[chunk_id].get("text", ""),
            score=scores[chunk_id] / max_score,
            source_filename=payloads[chunk_id].get("filename", ""),
            page_num=payloads[chunk_id].get("page_num"),
            metadata=payloads[chunk_id],
        )
        for chunk_id in sorted_ids
    ]
