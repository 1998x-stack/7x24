"""OpenAI Responses adapter. No network or model calls unless explicitly invoked."""

import json
import os
from news24.application.intelligence.prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT
from news24.domain.analysis import AnalysisCandidate, AnalysisSpec, ModelReply


class OpenAIResponsesProvider:
    """Use a configurable model; API credentials and model are never hard-coded."""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

    async def analyze(self, title: str | None, content: str, spec: AnalysisSpec) -> ModelReply:
        if spec.provider != "openai":
            raise ValueError("OpenAIResponsesProvider requires provider='openai'")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required; no silent neutral fallback")
        if len(content) > 12000:
            raise ValueError("input exceeds the configured max content length (12000)")
        from openai import AsyncOpenAI

        async with AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) as client:
            response = await client.responses.create(
                model=spec.model,
                store=False,
                instructions=SYSTEM_PROMPT,
                input=(
                    "TITLE:\n" + (title or "") + "\nCONTENT:\n" + content
                ),
                text={"format": {
                    "type": "json_schema", "name": "news24_analysis",
                    "strict": True, "schema": OUTPUT_SCHEMA,
                }},
                max_output_tokens=1200,
            )
        if response.status != "completed" or not response.output_text:
            raise RuntimeError("model did not return a completed structured response")
        output = AnalysisCandidate.model_validate(json.loads(response.output_text))
        usage = response.usage
        return ModelReply(
            data=output, response_id=response.id,
            input_tokens=usage.input_tokens if usage is not None else None,
            output_tokens=usage.output_tokens if usage is not None else None,
        )
