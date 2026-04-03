"""Anthropic LLM service — concrete implementation of LLMService."""
from __future__ import annotations

import json
import re
from typing import Any

from anthropic import AsyncAnthropic

from publicaition.services.base import LLMResponse, LLMService

# Default model — update as new Claude versions are released
DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicLLMService(LLMService):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def generate_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> Any:
        response = await self.generate(system, user, max_tokens)
        return _parse_json(response.text)


def _parse_json(text: str) -> Any:
    """Extract JSON from a response that may be wrapped in markdown code fences."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)
    return json.loads(text.strip())
