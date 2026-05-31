---
name: comparing-stocks
description: Side-by-side comparison of two or more stocks across news, financials, and filing dimensions. Use when the user asks to compare, contrast, or evaluate multiple stocks against each other.
---

# Comparing Stocks

## Procedure

1. Call relevant subagents per ticker in parallel. For a full comparison, call all three for each ticker:
   - news_macro for TICKER_A, then for TICKER_B
   - market_data for TICKER_A, then for TICKER_B
   - filings for TICKER_A, then for TICKER_B (if filing analysis is in scope)
3. Synthesize all responses into side-by-side sections below.

## Synthesis

Structure every section as a side-by-side comparison - not sequential per-ticker blocks. The Relative Assessment dimension table is required: name which company has the stronger position on each dimension and why. The executive summary states the overall comparative verdict in 3-4 sentences.

Reconcile conflicting signals across tickers. Cite Yahoo Finance data as "Source: Yahoo Finance".

## Output format

## {TICKER_A} vs {TICKER_B} - Comparative Research Report

### Executive Summary
[3-4 sentences: overall comparative verdict, which is stronger and the decisive factor]

### Financials Comparison
[Side-by-side key metrics from market_data for each ticker]

### News & Sentiment Comparison
[Side-by-side sentiment and key events from news_macro for each ticker]

### Filing Analysis Comparison
[Side-by-side qualitative findings from filings for each ticker - omit if filings not in scope]

### Relative Assessment
| Dimension | {TICKER_A} | {TICKER_B} | Edge |
|-----------|-----------|-----------|------|
| Valuation | | | |
| Growth | | | |
| Risk | | | |
| Sentiment | | | |

[1-2 sentences on overall winner and the single deciding factor]

### Sources
[All URLs deduplicated. Yahoo Finance data cited as "Source: Yahoo Finance"]
