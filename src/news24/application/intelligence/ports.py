"""Pure interface for asynchronous, injectable news analysis providers."""

from typing import Protocol

from news24.domain.analysis import AnalysisSpec, ModelReply

class AnalysisProvider(Protocol):
    async def analyze(self, title: str | None, content: str, spec: AnalysisSpec) -> ModelReply:
        """Return validated candidate JSON or raise an exception. Never synthesize neutral."""
