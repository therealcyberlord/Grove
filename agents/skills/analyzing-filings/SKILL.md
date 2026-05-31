---
name: analyzing-filings
description: Analyzes SEC 10-K annual filings for a stock ticker. Use when the user asks about annual reports, 10-K filings, risk factors, management tone, audit opinions, or governance.
---

# Analyzing Filings

## Procedure

1. Call the filings subagent, passing the ticker, user query, and form type "10-K" in the description.
2. Synthesize the response into the output format below.

Do not call news_macro or market_data for this query type.

Include form type "10-K" in the task description in addition to the ticker and user query.

## Synthesis

Present filing findings as returned. Surface red flags prominently. The executive summary covers: filing period, management tone verdict, and the most significant red flag if any. 2-3 sentences.

Cite sources as "Source: [section name]" per the subagent output.

## Output format

## {TICKER} - Filing Analysis

### Executive Summary
[2-3 sentences: filing period, management tone verdict, key red flag if present]

### Filing Analysis
[filings subagent findings verbatim, preserving all citations and red flag table]

### Investment Thesis
[Qualitative view based on filing alone. Primary governance risk and stated competitive moat.]

### Sources
[Section citations from subagent output]
