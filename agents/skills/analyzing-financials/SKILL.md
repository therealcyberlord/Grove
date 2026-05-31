---
name: analyzing-financials
description: Retrieves and analyzes quantitative market data for a stock ticker. Use when the user asks about financials, valuation multiples, earnings metrics (EPS, revenue figures), margins, cash flows, balance sheet, or capital allocation. Do not use for news, sentiment, or earnings call discussions.
---

# Analyzing Financials

## Procedure

1. Call the market_data subagent, passing the ticker and user query in the description.
2. Synthesize the response into the output format below.

Do not call news_macro or filings for this query type.

## Synthesis

Present the Financials section from market_data exactly as returned. Add brief contextual inline notes where relevant - do not alter any numbers. The executive summary highlights the single most important metric and the primary risk visible in the data. 2-3 sentences.

Cite Yahoo Finance data as "Source: Yahoo Finance".

## Output format

## {TICKER} - Financial Overview

### Executive Summary
[2-3 sentences: standout metric, key financial highlight, primary risk in the data]

### Financials
[market_data subagent findings, preserving all labels and values]

### Investment Thesis
[Bull/bear view based on financials alone. Single key metric and single key risk.]

### Sources
Source: Yahoo Finance
