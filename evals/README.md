# Grove Evals

Two eval suites: orchestrator end-to-end and subagent isolation. Both backed by Langfuse datasets and experiments.

## Orchestrator suite (`grove-orchestrator-v1`)

21 cases across 5 routing types. Each case runs the full orchestrator and scores the result.

| Routing type | Cases | Subagents called |
|---|---|---|
| `sentiment` | 7 | news_macro |
| `market_data` | 4 | market_data |
| `filings` | 3 | filings |
| `deep_dive` | 4 | all three |
| `comparison` | 3 | news_macro + market_data |

**Scorers:**
- `subagent_routing`: Jaccard similarity of expected vs detected subagents (tool fingerprinting)
- `no_fabricated_urls`: every URL in the report must appear in a tool result
- `helpfulness`: LLM judge (Gemini Flash Lite): does the report answer the query with ticker-specific data?

```bash
# Full suite
PYTHONPATH=. uv run python -m evals.experiments

# Filter by routing type
PYTHONPATH=. uv run python -m evals.experiments sentiment market_data
```

## Subagent suite (`grove-subagent-v1`)

6 cases, 2 per subagent. Bypasses the orchestrator and runs each subagent directly.

**Scorers:**
- `no_fabricated_urls`: same URL check as orchestrator
- `subagent_quality`: LLM judge (Gemini Flash Lite): per-subagent rubric covering required content and citation style

```bash
# Full suite
PYTHONPATH=. uv run python -m evals.experiments subagent

# Filter by subagent
PYTHONPATH=. uv run python -m evals.experiments subagent news_macro
```

## Cost notes

`deep_dive` and `comparison` cases are the most expensive as each runs 2-3 subagents with multiple tool calls. Use routing type filters during iterative development. The LLM judges use Gemini Flash Lite to keep eval cost low. The online Langfuse evaluator fires on production traces at 10% sampling.
