"""Compatibility facade; use application ports and infrastructure LLM adapter."""

from news24.application.intelligence.ports import AnalysisProvider
from news24.application.intelligence.prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT
from news24.infrastructure.llm.openai_responses import OpenAIResponsesProvider

__all__ = ["AnalysisProvider", "OUTPUT_SCHEMA", "SYSTEM_PROMPT", "OpenAIResponsesProvider"]
