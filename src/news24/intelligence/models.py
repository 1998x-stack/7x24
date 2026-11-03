"""Strict schemas: probabilities are not facts and quotes are not semantic proof."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "negative", "neutral", "unknown"]


class CandidateClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=400)
    quote: str = Field(min_length=1, max_length=300)


class AnalysisCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentiment: Sentiment
    claims: list[CandidateClaim] = Field(max_length=5)


class ModelReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AnalysisCandidate
    response_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AnalysisSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = "news24-evidence-v1"
    schema_version: str = "1"
