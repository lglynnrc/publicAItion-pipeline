"""FastAPI application — wires services and mounts routes."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from publicaition.api.routes import router
from publicaition.services.container import Services
from publicaition.services.evaluation import PublicAItionEvaluationService
from publicaition.services.few_shot import PublicAItionFewShotService
from publicaition.services.guidelines import PublicAItionGuidelinesService
from publicaition.services.llm import AnthropicLLMService
from publicaition.services.retrieval import QdrantRetrievalService
from publicaition.services.templates import PublicAItionTemplateService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    llm = AnthropicLLMService(api_key=api_key)

    app.state.services = Services(
        retrieval=QdrantRetrievalService(url=qdrant_url, api_key=qdrant_api_key),
        llm=llm,
        evaluation=PublicAItionEvaluationService(llm=llm),
        templates=PublicAItionTemplateService(),
        few_shot=PublicAItionFewShotService(),
        guidelines=PublicAItionGuidelinesService(llm=llm),
    )

    # In-memory run store: run_id → PipelineState
    # Replace with database-backed store when deploying as a service (N-11)
    app.state.runs = {}

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="publicaition-pipeline",
        description="Manuscript generation pipeline API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
