# ADR-0004: versioned model candidates, exact citations and conservative event links

Status: proposed — V0.5

## Why

V0.3 persisted raw source news and revisions. V0.4 created a durable task engine, but the analyze job was intentionally unimplemented. Older sentiment code silently returned 0 (neutral) on API failures and had no link to supporting source spans or prompt versions.

## Decision

1. Model work is opt-in and asynchronous: a queued `analyze` job consumes one stored news item. No key or explicit model configuration means failure, not a fallback neutral score.
2. Use an injectable AnalysisProvider protocol and a bounded OpenAI **Responses** adapter. The server requests a strict JSON schema; local Pydantic checks the result again. The actual SDK/network contract requires a separate smoke check in a configured account.
3. The model suggests tone and up to five candidate claims. Claims supply exact verbatim quotes. The local verifier only reports **TEXT_MATCH_ONLY**, **NOT_FOUND**, or **AMBIGUOUS**, returning offsets for a single exact quote occurrence.
4. Lexical quote matches do not establish semantic entailment. Model-extracted statements are **not** certified facts and must not be turned into investing signals.
5. Persist source revision, model, provider, prompt version **and SHA-256**, output schema version, input hash, response ID, token use, structured output and evidence spans.
6. Analyze identity hashes the entire configuration. On source edits, a fresh analysis is required; stale model replies are rejected before transaction commit. Repeated same-revision same-config executions are cached.
7. Candidate clusters only match identical sufficiently specific quotes within a Shanghai-local day. No embeddings, fuzzy auto-merges or inferred source independence. Only current non-deleted revisions count toward active clusters.
8. Do not make AI a prerequisite of ingestion or deterministic daily reporting. A rejected claim makes the queued task fail visibly and does not silently count as success.

## Deferred

Human verification workflow, deeper semantic entailment checks, benchmarked semantic deduplication, independent-source lineage, live model evaluation, budget/rate-limit enforcement and Web UI belong to subsequent stages. Before deployment, evaluate API key handling, privacy, source redistribution rights, token cost and rate limits.
